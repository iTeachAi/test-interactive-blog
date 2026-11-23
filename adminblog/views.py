from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView, DetailView, ListView, UpdateView, DeleteView
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse_lazy, reverse

from .models import Topic, BlogQuestions, Blog
from .services import generate_topics, generate_blog, attach_blog_image


from django.contrib.auth.mixins import PermissionRequiredMixin

class AdminBlogAccessMixin(PermissionRequiredMixin):
    permission_required = "adminblog:access_adminblog"
    raise_exception = True


class BaseTemplate(View):
    template_name='adminblog/base.html'
    def get_context_data(self, **kwargs):
                context = super().get_context_data(**kwargs)
                topics = Topic.objects.all()
                blogs = Blog.objects.all()
                context['topics'] = topics
                context['blogs'] = blogs
                return context

# Create your views here.
class BlogHomeView(AdminBlogAccessMixin, TemplateView):
    template_name = 'adminblog/home.html'
    def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            topics = Topic.objects.all()
            context['topics'] = topics
            return context
class SelectTopicView(AdminBlogAccessMixin, TemplateView):
    template_name = "adminblog/select_topic.html"
    def get_suggestions(self, topic_request):
        suggestions = topic_request.suggested_topics or []

        if not isinstance(suggestions, list):
            return []

        return suggestions[:5]

    def get(self, request, id):
        topic_request = get_object_or_404(
            Topic,
            id=id,
        )

        return render(
            request,
            self.template_name,
            {
                "topic_request": topic_request,
                "generated_topics": self.get_suggestions(topic_request),
            },
        )

    def post(self, request, id):
        topic_request = get_object_or_404(
            Topic,
            id=id,
        )
        generated_topics = self.get_suggestions(topic_request)

        try:
            selected_index = int(request.POST["topic_index"])
            selected_topic = generated_topics[selected_index]
        except(KeyError, ValueError, IndexError):
            messages.error(request, "Please select a valid topic")
            return redirect(
                'adminblog:select_topic',
                id=id,
            )

        questions = selected_topic.get('questions', [])

        if len(questions) < 5:
            messages.error(
                request,
                "The selected topic does not contain five questions ",
            )

            return redirect(
                "adminblog:select_topic",
                id=id,
            )

        blog_questions, created = BlogQuestions.objects.get_or_create(
            topic_request=topic_request,
            generated_topic=selected_topic.get('topic', ''),
            defaults={
                'principle': selected_topic.get('principle', ''),
                'question1': questions[0],
                'question2': questions[1],
                'question3': questions[2],
                'question4': questions[3],
                'question5': questions[4],
            },
        )

        return redirect(
            'adminblog:answer_questions',
            id=blog_questions.id,
        )
    
    
class CreateTopicView(AdminBlogAccessMixin, CreateView):
    template_name = 'adminblog/create_topic.html'
    model = Topic
    fields = [
        "name",
        "lesson_description"
    ]
    pk_url_kwarg = 'id'
    def get_success_url(self):
        return reverse('adminblog:select_topic',
                            kwargs={'id': self.object.id})

    def form_valid(self, form):
        response = super().form_valid(form)

        try:
            result = generate_topics(
                lesson_description = self.object.lesson_description,
            )

            self.object.suggested_topics = result
            self.object.generation_error = ""

            self.object.save(
                update_fields = [
                    "suggested_topics",
                    "generation_error",
                ]
            )

            # generate_topics = result[0]["output"]

            # for generated_topic in generate_topics:

            #     questions = generated_topic.get("questions", [])

            #     if len(questions) != 5:
            #         continue

            #     BlogQuestions.objects.update_or_create(
            #         topic_request=self.object,
            #         generated_topic=generated_topic.get("topic", ""),
            #         defaults={
            #             "principle": generated_topic("principle", ""),
            #             "question1": questions[0],
            #             "question2": questions[1],
            #             "question3": questions[2],
            #             "question4": questions[3],
            #             "question5": questions[4],
            #         }
            #     )


            # messages.success(
            #     self.request,
            #     "The blog topics were generated successfully!"
            # )
        except Exception as error:
             self.object.generation_error = str(error)

             self.object.save(
                 update_fields = [
                     "generation_error",
                 ]
             )
        return response

class DetailTopicView(DetailView):
    model = Topic
    pk_url_kwarg = 'id'
    template_name = 'adminblog/topic_details.html'
    context_object_name = 'topic'

class DeleteTopicView(DeleteView):
    model = Topic
    pk_url_kwarg = 'id'
    template_name = 'adminblog/delete_topic.html'
    success_url = reverse_lazy('adminblog:home')


class BlogQuestionsView(UpdateView):
    model = BlogQuestions
    pk_url_kwarg = 'id'
    template_name = 'adminblog/blog_questions.html'
    context_object_name = 'blog_questions'
    fields = [
        'answer1',
        'answer2',
        'answer3',
        'answer4',
        'answer5',

    ]

    def get_success_url(self):
        messages.success(
            self.request,
            "Your answeres were saved.",
        )

        return reverse(
            'adminblog:answer_questions',
            kwargs={'id': self.object.id},
        )
    

class GenerateBlogView(AdminBlogAccessMixin, View):
    def post(self, request, id):
        blog_questions = get_object_or_404(
            BlogQuestions,
            id=id,
        )

        answers=[
            blog_questions.answer1,
            blog_questions.answer2,
            blog_questions.answer3,
            blog_questions.answer4,
            blog_questions.answer5,
        ]

        if any(not answer.strip() for answer in answers):
            messages.error(
                request,
                "Please answerd all five questions before generating the blog. "
            )

            return redirect(
                "adminblog:answer_questions",
                id=blog_questions.id,
            )

        try:
            result = generate_blog(blog_questions)

            blog, created = Blog.objects.update_or_create(
                blog_questions = blog_questions,
                defaults={
                    "name": result.get(
                        "name",
                        blog_questions.generated_topic,
                    ),
                    "category": result.get(
                        "category",
                        "Basketball",
                    ),
                    "summary": result.get("summary", ""),
                    "content": result.get("content", ""),
                    "author": result.get("author", "MO"),
                },
            )

            image_url = result.get("image_url")

            if image_url:
                attach_blog_image(blog, image_url)

        except Exception as error:
            messages.error(
                request,
                f"The blog could not be generated: {error}",
            )

            return redirect(
                "adminblog:answer_questions",
                id=blog_questions.id,
            )

        if created:
            messages.success(
                request,
                "The blog was generated successfully.",
            )
        else:
            messages.success(
                request,
                "The blog was regenerated successfully. "
            )

        return redirect(
            "adminblog:blog_detail",
            id=blog.id
        )



class BlogDetailView(AdminBlogAccessMixin, DetailView):
    model = Blog
    pk_url_kwarg = 'id'
    template_name = 'adminblog/blog_detail.html'
    context_object_name = 'blog'

class BlogListView(AdminBlogAccessMixin, ListView):
    model = Blog
    template_name = 'adminblog/blog_list.html'
    context_object_name = 'blogs'

    def get_queryset(self):
        return Blog.objects.order_by("-date", "-time")