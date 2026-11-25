from django import forms
from django.conf import settings
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.text import Truncator, normalize_newlines
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DetailView, TemplateView

from backend.lessons import lesson_body
from backend.forms import ConsultationRequestForm
from backend.models import Audience, BlogPost, CourtTerm, VideoLesson
from backend.webhook import BlogWebhookError, request_webhook_output

from .stat_sheet import analyze_rows, read_csv, stat_highlights


class BlogArchiveView(TemplateView):
    template_name = 'frontendblog/archive.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = {}
        featured = None
        for post in BlogPost.objects.public():
            entry = {
                'title': post.title,
                'summary': post.summary or Truncator(post.body).words(32),
                'url': post.get_absolute_url(),
                'image_url': post.image_url,
                'image_alt': post.image_alt,
                'date': post.date,
                'author': post.author,
                'category': post.category,
            }
            sections.setdefault(post.category, []).append(entry)
            if featured is None:
                featured = entry

        selected = self.request.GET.get('category', '')
        if selected not in sections:
            selected = ''
        context['categories'] = sorted(sections, key=str.casefold)
        context['selected_category'] = selected
        context['featured'] = sections[selected][0] if selected else featured
        context['sections'] = [
            {'title': category, 'entries': entries}
            for category, entries in sections.items()
            if not selected or category == selected
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
        return posts.public()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_coach_article'] = self.object.audiences.filter(pk=Audience.Role.COACH).exists()
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

def home(request):
    if 'category' in request.GET:
        return BlogArchiveView.as_view()(request)
    return render(request, 'frontendblog/index.html')


def audience_blog(request, role):
    audience = get_object_or_404(Audience, pk=role)
    return render(request, 'frontendblog/audience.html', {
        'audience': audience,
        'posts': BlogPost.objects.public().filter(audiences=audience),
    })


def court_lingo(request):
    query = request.GET.get('q', '').strip()[:150]
    terms = CourtTerm.objects.all()
    for word in query.split():
        terms = terms.filter(Q(name__icontains=word) | Q(aliases__icontains=word))
    return render(request, 'frontendblog/lingo.html', {'terms': terms, 'query': query})


def term_detail(request, slug):
    term = get_object_or_404(CourtTerm, slug=slug)
    return render(request, 'frontendblog/term.html', {
        'term': term,
        'articles': term.articles.public(),
        'videos': term.videolesson_set.all(),
    })


@require_http_methods(['GET', 'HEAD'])
@xframe_options_sameorigin
def court_term_pdf(request, slug):
    term = get_object_or_404(CourtTerm, slug=slug)
    if not term.pdf:
        raise Http404
    try:
        document = term.pdf.open('rb')
    except FileNotFoundError as error:
        raise Http404 from error
    return FileResponse(document, content_type='application/pdf', filename=f'{term.slug}.pdf')


def video_lessons(request):
    lessons = VideoLesson.objects.all()
    topics = lessons.order_by('topic').values_list('topic', flat=True).distinct()
    selected_topic = request.GET.get('topic', '')
    role = request.GET.get('audience', '')
    if selected_topic:
        lessons = lessons.filter(topic=selected_topic)
    if role:
        lessons = lessons.filter(audiences=role)
    return render(request, 'frontendblog/videos.html', {
        'lessons': lessons.prefetch_related(Prefetch('articles', queryset=BlogPost.objects.public()), 'terms'),
        'topics': topics,
        'audiences': Audience.Role.choices,
        'selected_topic': selected_topic,
        'selected_role': role,
    })


def configured_url(value):
    try:
        URLValidator(schemes=['http', 'https'])(value)
    except ValidationError:
        return ''
    return value


class StatSheetForm(forms.Form):
    statsheet_type = forms.ChoiceField(
        label='Stat sheet type',
        choices=(('', 'Choose a type'), ('game', 'Game stat sheet'), ('team', 'Team stat sheet')),
    )
    focus_team = forms.ChoiceField(
        label='Which team should the analysis focus on?',
        choices=(('', 'Choose a side'), ('home', 'Home'), ('away', 'Away')),
        required=False,
        help_text='Required for game stat sheets.',
    )
    sheet = forms.FileField(label='Upload a CSV stat sheet', widget=forms.FileInput(attrs={'accept': '.csv,text/csv'}))

    webhook_analysis = ''
    webhook_error = ''

    @property
    def sends_csv(self):
        return bool(settings.N8N_TEST_WEBHOOK_URL)

    def clean_focus_team(self):
        if self.cleaned_data.get('statsheet_type') != 'game':
            return ''
        focus_team = self.cleaned_data['focus_team']
        if not focus_team:
            raise forms.ValidationError('Choose Home or Away for a game stat sheet.')
        return focus_team

    def statsheet_metadata(self):
        metadata = {'statsheet_type': self.cleaned_data['statsheet_type']}
        if metadata['statsheet_type'] == 'game':
            metadata['focus_team'] = self.cleaned_data['focus_team']
        return metadata

    def clean_sheet(self):
        sheet = self.cleaned_data['sheet']
        if sheet.size > 256 * 1024:
            raise forms.ValidationError('Upload a CSV no larger than 256 KiB.')
        try:
            csv_text = read_csv(sheet)
            players = analyze_rows(csv_text, allow_team_rows=self.cleaned_data.get('statsheet_type') == 'team')
        except ValueError as error:
            raise forms.ValidationError(str(error)) from error

        if self.sends_csv and not self.errors:
            try:
                result = request_webhook_output(
                    settings.N8N_TEST_WEBHOOK_URL,
                    {'task': 'statsheet', 'csv': csv_text, **self.statsheet_metadata()},
                )
            except BlogWebhookError:
                self.webhook_error = 'The analysis service could not process the CSV. The local breakdown is shown below.'
            else:
                analysis = result.get('analysis')
                if isinstance(analysis, str):
                    self.webhook_analysis = analysis.strip()
        return players


@require_http_methods(['GET', 'HEAD', 'POST'])
def analyzer(request):
    form = StatSheetForm(request.POST, request.FILES) if request.method == 'POST' else StatSheetForm()
    players = form.cleaned_data['sheet'] if form.is_valid() else None
    return render(request, 'frontendblog/analyzer.html', {
        'analyzer_url': configured_url(settings.STAT_SHEET_ANALYZER_URL),
        'form': form,
        'players': players,
        'highlights': stat_highlights(players) if players else [],
    })


class ConsultationView(CreateView):
    form_class = ConsultationRequestForm
    template_name = 'frontendblog/consultation.html'
    success_url = reverse_lazy('consultation-received')

    def dispatch(self, request, *args, **kwargs):
        booking_url = configured_url(settings.CONSULTATION_BOOKING_URL)
        if request.method in ('GET', 'HEAD') and booking_url:
            return redirect(booking_url)
        return super().dispatch(request, *args, **kwargs)
