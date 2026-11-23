from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.text import Truncator, normalize_newlines
from django.views.generic import DetailView, TemplateView

from backend.lessons import lesson_body
from backend.models import BlogPost


class BlogHomeView(TemplateView):
    template_name = 'frontendblog/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = {}
        for post in BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED):
            sections.setdefault(post.category, []).append({
                'title': post.title,
                'summary': post.summary or Truncator(post.body).words(32),
                'url': post.get_absolute_url(),
                'image_url': post.image_url,
                'image_alt': post.image_alt,
                'date': post.date,
                'author': post.author,
            })
        context['sections'] = [
            {'title': category, 'entries': entries}
            for category, entries in sections.items()
        ]
        return context


class BlogDetailView(DetailView):
    model = BlogPost
    context_object_name = 'post'
    template_name = 'frontendblog/blog_detail.html'

    def get_queryset(self):
        user = self.request.user
        posts = super().get_queryset()
        if user.is_staff and (
            user.has_perm('backend.change_blogpost')
            or user.has_perm('backend.add_blogpost')
            or user.has_perm('backend.delete_blogpost')
        ):
            return posts
        return posts.filter(status=BlogPost.Status.PUBLISHED)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.object.lesson
        if not lesson or normalize_newlines(self.object.body) != normalize_newlines(
            lesson_body(lesson['post']).strip()
        ):
            return context

        article = lesson['post']
        visuals = {}
        validate_url = URLValidator(schemes=['https'])
        raw_visuals = lesson.get('visuals')
        if isinstance(raw_visuals, list):
            for visual in raw_visuals:
                if not isinstance(visual, dict) or not isinstance(visual.get('key'), str):
                    continue
                url = visual.get('asset_url')
                if not isinstance(url, str):
                    continue
                try:
                    validate_url(url)
                except ValidationError:
                    continue
                visuals[visual['key']] = visual

        context['lesson_article'] = article
        context['learning_objective'] = lesson['classification'].get('learning_objective')
        context['cover_visuals'] = [
            visual for visual in visuals.values()
            if isinstance(visual.get('placements'), list) and 'cover' in visual['placements']
        ]
        context['lesson_sections'] = [
            {
                **section,
                'visuals': [
                    visuals[key] for key in section['visual_keys']
                    if isinstance(key, str) and key in visuals
                ] if isinstance(section.get('visual_keys'), list) else [],
            }
            for section in article['sections']
        ]
        return context
