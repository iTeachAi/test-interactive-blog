import requests
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import TemplateView, DetailView
from django.views.generic.edit import FormView, CreateView, UpdateView

from urllib.parse import urlencode
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
# Create your views here.
from .forms import (
    RegisterForm, 
    ParticipantTypeForm, 
    AnswerQuestionForm, 
    EmailAuthenticationForm,
)
from .services import generate_question, generate_personalized_blog

from django.utils.http import url_has_allowed_host_and_scheme
from .models import AiGenerated, BlogAnswer, PersonalizedBlog
from adminblog.models import Blog

# ---- Start of Views ------
class RegisterView(FormView):
    template_name = "registration/register.html"
    form_class = RegisterForm

    def form_valid(self, form):
        user = form.save()

        login(self.request, user)
        next_url = self.request.POST.get(
            "next",
            self.request.GET.get("next", ""),
        )

        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("home")


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] =self.request.GET.get("next", "")
        return context


class EmailLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class HomeView(TemplateView):
    template_name = 'app/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["blogs"] = Blog.objects.all()

        if self.request.user.is_authenticated:
            context["personalized_blog_ids"] = set(
                PersonalizedBlog.objects
                .filter(answer__session__user = self.request.user)
                .values_list("answer__blog_id", flat=True)
            )
        else:
            context["personalized_blog_ids"] = set()

        return context

class ChooseBlogView(LoginRequiredMixin, View):
    def get(self, request, blog_id):
        blog = get_object_or_404(
            Blog,
            pk=blog_id
        )
        personalized_blog = (
            PersonalizedBlog.objects
            .filter(
                answer__blog = blog,
                answer__session__user = request.user,
            )
            .order_by("-created_at")
            .first()
        )

        if personalized_blog:
            return redirect(
                "personalized_blog",
                pk=personalized_blog.pk
            )

        return redirect(
            "user_type",
            blog_id=blog.pk
        )

class SelectUserTypeView(LoginRequiredMixin, CreateView):
    model = AiGenerated
    template_name = 'app/select_type.html'
    form_class = ParticipantTypeForm

    def dispatch(self, request, *args, **kwargs):
        self.selected_blog = get_object_or_404(
            Blog,
            id=self.kwargs["blog_id"],
        )

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user_type = form.cleaned_data["user_type"]

        try:
            question_text = generate_question(
                user_type=user_type,
                blog_content=self.selected_blog.content,
            )
        except Exception as error:
            form.add_error(
                None,
                f"The question could not be generated: {error}",
            )
            return self.form_invalid(form)

        if not question_text:
            form.add_error(
                None,
                "The webhook did not generate a question.",
            )

            return self.form_invalid(form)

        
        if not question_text.strip():
            form.add_error(
                None,
                "The webhook returned an invalid question.",
            )
            return self.form_invalid(form)

        # Create AiGenerated Session
        self.object = form.save(commit=False)
        self.object.user = self.request.user
        self.object.blog = self.selected_blog
        self.object.save()

        # Create the question/answer record
        self.answer_object = BlogAnswer.objects.create(
            session = self.object,
            blog= self.selected_blog,
            question = question_text,
        )
        return HttpResponseRedirect(self.get_success_url())

    
    def get_success_url(self):
        return reverse(
            "user_question",
            kwargs={"pk": self.answer_object.pk},
        )

class UserAnswerView(LoginRequiredMixin, UpdateView):
    model = BlogAnswer
    template_name = 'app/question.html'
    form_class = AnswerQuestionForm



    def form_valid(self, form):
        self.object = form.save()

        existing_blog = (
            PersonalizedBlog.objects
            .filter(answer=self.object)
            .first()
        )

        if existing_blog:
            messages.info(
                self.request,
                "Your personalized blog has already been generated."
            )

            return redirect(
                "personalized_blog",
                pk=existing_blog.pk,
            )

        try:
            result = generate_personalized_blog(
                self.object,
                )

            personalized_blog, created = (
                PersonalizedBlog.objects.update_or_create(
                    answer=self.object,
                    defaults={
                        "title": result.get(
                            "title",
                            f"Personalized: {self.object.blog.name}",
                        ),
                        "summary": result.get("summary", ""),
                        "content": result["content"],
                    },
                )
            )

            self.personalized_blog = personalized_blog

            self.request.session["personalized_blog_id"] = (
                personalized_blog.pk
            )

            messages.success(
                self.request,
                "Your personalized blog was created"
            )
        except Exception as error:
            self.request.session.pop(
                "personalized_blog_id",
                None,
            )

            messages.error(
                self.request,
                f"Your answer was saved, but the blog was not created"
                f"{error}",
            )

        return HttpResponseRedirect(self.get_success_url())

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        existing_blog = (
            PersonalizedBlog.objects
            .filter(answer=self.object)
            .first()
        )

        if existing_blog:
            return redirect(
                "personlized_blog",
                pk=existing_blog.pk,
            )

        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
            return BlogAnswer.objects.filter(
                    session__user = self.request.user
                )
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["question"] = self.object.question
        return context

    def get_success_url(self):
        if hasattr(self, "personalized_blog"):
            return reverse(
                "personalized_blog", 
                kwargs={"pk": self.personalized_blog.pk})
        return reverse(
            "blog_answers", 
            kwargs={"blog_id": self.object.blog_id})


class BlogAnswersView(LoginRequiredMixin, DetailView):
    model = Blog
    template_name = "app/answer.html"
    context_object_name = "blog"
    pk_url_kwarg = "blog_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["random_pairs"] = (
            self.object.question_answers
            .exclude(answer="")
            .order_by("?")[:3]
        )
        personalized_blog_id = self.request.session.get(
            "personalized_blog_id"
        )

        context["personalized_blog"]= None

        if personalized_blog_id:
            context["personalized_blog"] = (
                PersonalizedBlog.objects
                .filter(
                    pk=personalized_blog_id,
                    answer__blog=self.object,
                )
                .first()
            )
        return context


class PersonalizedBlogDetailView(LoginRequiredMixin, DetailView):
    model = PersonalizedBlog
    template_name = "app/personalized_blog.html"
    context_object_name = "personalized_blog"

    def get_queryset(self):
        return(
            PersonalizedBlog.objects
            .filter(answer__session__user = self.request.user)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["question"] = self.object.answer.question
        return context

    