from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Audience(models.Model):
    class Role(models.TextChoices):
        PLAYER = 'player', 'Player'
        COACH = 'coach', 'Coach'
        PARENT = 'parent', 'Parent'

    slug = models.CharField(max_length=6, choices=Role.choices, primary_key=True)

    def __str__(self):
        return self.get_slug_display()


class BlogPostQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status=BlogPost.Status.PUBLISHED, date__lte=timezone.localdate())


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        APPROVED = 'approved', 'Approved'
        PUBLISHED = 'published', 'Published'

    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    audiences = models.ManyToManyField(Audience, blank=True)
    topics = models.CharField(max_length=500, blank=True, help_text='Separate additional topics with commas.')
    category = models.CharField(max_length=50)
    author = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
    body = models.TextField()
    date = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PUBLISHED)
    lesson = models.JSONField(default=dict, blank=True, editable=False)
    image_url = models.URLField(max_length=2048, blank=True, editable=False)
    image_alt = models.CharField(max_length=250, blank=True, editable=False)

    objects = BlogPostQuerySet.as_manager()

    class Meta:
        ordering = ('-date', '-pk')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f'{slugify(self.title)[:150] or "article"}-{uuid4().hex[:16]}'
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = {*kwargs['update_fields'], 'slug'}
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog-detail', kwargs={'slug': self.slug})


def validate_term_pdf(upload):
    if upload.size > 20 * 1024 * 1024:
        raise ValidationError('Choose a PDF no larger than 20 MiB.')
    position = upload.tell()
    try:
        upload.seek(0)
        header = upload.read(8)
        upload.seek(max(0, upload.size - 1024))
        trailer = upload.read()
    finally:
        upload.seek(position)
    if not header.startswith(b'%PDF-') or not trailer.rstrip().endswith(b'%%EOF'):
        raise ValidationError('Choose a valid PDF document.')


class CourtTerm(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    aliases = models.CharField(max_length=300, blank=True)
    meaning = models.TextField(blank=True)
    pdf = models.FileField(
        upload_to='court-lingo/',
        blank=True,
        max_length=250,
        validators=[FileExtensionValidator(['pdf']), validate_term_pdf],
        help_text='PDF up to 20 MiB. The file will be publicly visible on the term page.',
    )
    when_to_use = models.TextField(blank=True)
    on_court = models.TextField(blank=True)
    articles = models.ManyToManyField(BlogPost, blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.meaning and not self.pdf:
            raise ValidationError('Add a definition or upload a PDF.')


class VideoLesson(models.Model):
    title = models.CharField(max_length=150)
    objective = models.TextField()
    topic = models.CharField(max_length=100, db_index=True)
    audiences = models.ManyToManyField(Audience, blank=True)
    source_url = models.URLField()
    articles = models.ManyToManyField(BlogPost, blank=True)
    terms = models.ManyToManyField(CourtTerm, blank=True)

    class Meta:
        ordering = ('topic', 'title')

    def __str__(self):
        return self.title


class ConsultationRequest(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    role = models.CharField(max_length=6, choices=Audience.Role.choices)
    question = models.TextField(max_length=3000)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-submitted_at',)

    def __str__(self):
        return f'{self.name} ({self.get_role_display()})'
