from django.db import models
from django.urls import reverse


class BlogPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        APPROVED = 'approved', 'Approved'
        PUBLISHED = 'published', 'Published'

    title = models.CharField(max_length=150)
    category = models.CharField(max_length=50)
    author = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
    body = models.TextField()
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PUBLISHED)
    lesson = models.JSONField(default=dict, blank=True, editable=False)
    image_url = models.URLField(max_length=2048, blank=True, editable=False)
    image_alt = models.CharField(max_length=250, blank=True, editable=False)

    class Meta:
        ordering = ('-date', '-pk')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog-detail', kwargs={'pk': self.pk})
