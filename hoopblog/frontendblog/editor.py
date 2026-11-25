from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from backend.forms import BlogPostForm, CourtTermEditorForm, NewBlogPostForm
from backend.models import BlogPost, CourtTerm
from backend.webhook import BlogWebhookError, generate_blog_image, process_blog_post


class BlogEditorAccessMixin(UserPassesTestMixin):
    login_url = reverse_lazy('admin:login')
    editor_permissions = ()

    def test_func(self):
        user = self.request.user
        return user.is_active and user.is_staff and (
            not self.editor_permissions or any(user.has_perm(permission) for permission in self.editor_permissions)
        )


class BlogEditorView(BlogEditorAccessMixin, ListView):
    editor_permissions = ('backend.add_blogpost', 'backend.change_blogpost', 'backend.delete_blogpost')
    model = BlogPost
    queryset = BlogPost.objects.prefetch_related('audiences')
    context_object_name = 'posts'
    template_name = 'frontendblog/editor/index.html'


class BlogCreateView(BlogEditorAccessMixin, SuccessMessageMixin, CreateView):
    editor_permissions = ('backend.add_blogpost',)
    model = BlogPost
    form_class = NewBlogPostForm
    template_name = 'frontendblog/editor/form.html'
    success_url = reverse_lazy('blog-editor')
    success_message = 'Post processed and saved.'

    def form_valid(self, form):
        submission_type = 'file' if form.cleaned_data.get('source_file') is not None else 'text'
        try:
            post_data = process_blog_post(form.cleaned_data['body'], submission_type=submission_type)
        except BlogWebhookError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)

        audiences = post_data.pop('audiences', [])
        for field, value in post_data.items():
            setattr(form.instance, field, value)
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.audiences.set(audiences)
        return response


class BlogUpdateView(BlogEditorAccessMixin, SuccessMessageMixin, UpdateView):
    editor_permissions = ('backend.change_blogpost',)
    model = BlogPost
    fields = (*BlogPostForm.Meta.fields, 'status', 'date', 'audiences', 'topics')
    template_name = 'frontendblog/editor/form.html'
    success_url = reverse_lazy('blog-editor')
    success_message = 'Post updated.'


class BlogGenerateImageView(BlogEditorAccessMixin, View):
    editor_permissions = ('backend.change_blogpost',)

    def post(self, request, pk):
        eligible = BlogPost.objects.filter(pk=pk, status=BlogPost.Status.APPROVED, image_url='')
        post = get_object_or_404(BlogPost, pk=pk)
        if post.status != BlogPost.Status.APPROVED or post.image_url:
            messages.error(request, 'Image generation is available for approved posts without a cover image.')
            return redirect('blog-editor')

        try:
            image = generate_blog_image(post)
        except BlogWebhookError as error:
            messages.error(request, str(error))
        else:
            if eligible.update(**image):
                messages.success(request, 'Cover image added.')
            else:
                messages.error(request, 'The post changed while the image was being generated.')
        return redirect('blog-editor')


class BlogDeleteView(BlogEditorAccessMixin, SuccessMessageMixin, DeleteView):
    editor_permissions = ('backend.delete_blogpost',)
    http_method_names = ('get', 'head', 'post', 'options')
    model = BlogPost
    template_name = 'frontendblog/editor/confirm_delete.html'
    success_url = reverse_lazy('blog-editor')
    success_message = 'Post deleted.'

class CourtTermEditorView(BlogEditorAccessMixin, ListView):
    editor_permissions = ('backend.add_courtterm', 'backend.change_courtterm', 'backend.view_courtterm')
    model = CourtTerm
    context_object_name = 'terms'
    template_name = 'frontendblog/editor/terms.html'


class CourtTermFormMixin(BlogEditorAccessMixin, SuccessMessageMixin):
    model = CourtTerm
    form_class = CourtTermEditorForm
    template_name = 'frontendblog/editor/term_form.html'
    success_url = reverse_lazy('editor-court-lingo')


class CourtTermCreateView(CourtTermFormMixin, CreateView):
    editor_permissions = ('backend.add_courtterm',)
    success_message = 'Court Lingo entry added.'


class CourtTermUpdateView(CourtTermFormMixin, UpdateView):
    editor_permissions = ('backend.change_courtterm',)
    success_message = 'Court Lingo entry updated.'
