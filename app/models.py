from django.db import models
from adminblog.models import Blog
# Create your models here.

from django.conf import settings

class AiGenerated(models.Model):
    USER_CHOICES = {
        'parent':'parent',
        'coach':'coach',
        'player':'player',
        'owner/organization':'owner/organization',
        'athletic director':'athletic director',
        'trainer':'trainer',
        'fan':'fan',
    }
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generated_sessions",
        null=True,
        blank=True,
    )
    user_type = models.CharField(max_length=100, choices=USER_CHOICES)
    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name='ai_generated_answers',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

class BlogAnswer(models.Model):
    session = models.ForeignKey(
        "AiGenerated",
        on_delete=models.CASCADE,
        related_name='answers',
    )
    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name='question_answers'
    )
    question = models.CharField(
        max_length=500, 
        blank=True,
        null=True,
        editable=False)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class PersonalizedBlog(models.Model):
    answer = models.OneToOneField(
        BlogAnswer,
        on_delete=models.CASCADE,
        related_name="personalized_blog",
    )
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def image(self):
            return self.answer.blog.image