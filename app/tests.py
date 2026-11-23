from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from adminblog.models import Blog, BlogQuestions, Topic
from app.models import AiGenerated


class SelectUserTypeViewTests(TestCase):
    def setUp(self):
        topic = Topic.objects.create(
            name="Ball movement",
            lesson_description="How to create advantages with passing.",
        )
        blog_questions = BlogQuestions.objects.create(
            topic_request=topic,
            generated_topic="Teaching extra passes",
            principle="Move the defense before the shot.",
            question1="Q1",
            answer1="",
            question2="Q2",
            answer2="",
            question3="Q3",
            answer3="",
            question4="Q4",
            answer4="",
            question5="Q5",
            answer5="",
        )
        self.blog = Blog.objects.create(
            blog_questions=blog_questions,
            name="Drive and kick reads",
            category="Offense",
            summary="Use paint touches to trigger rotations.",
            content="Paint touches force help and open the next pass.",
            author="Coach AI",
        )

    @patch("app.views.generate_question")
    def test_submit_type_generates_question_and_redirects(self, mock_generate_question):
        mock_generate_question.return_value = "What do you look for after the help defender commits?"

        response = self.client.post(
            reverse("user_type", kwargs={"blog_id": self.blog.id}),
            data={"user_type": "coach"},
        )

        self.assertRedirects(
            response,
            reverse("user_question", kwargs={"pk": AiGenerated.objects.get().pk}),
        )

        ai_generated = AiGenerated.objects.get()
        self.assertEqual(ai_generated.blog, self.blog)
        self.assertEqual(ai_generated.user_type, "coach")
        self.assertEqual(
            ai_generated.question,
            "What do you look for after the help defender commits?",
        )
        mock_generate_question.assert_called_once_with(
            user_type="coach",
            blog_content=self.blog.content,
        )

    @patch("app.views.generate_question")
    def test_submit_type_shows_form_error_when_question_generation_fails(self, mock_generate_question):
        mock_generate_question.side_effect = ValueError("invalid webhook payload")

        response = self.client.post(
            reverse("user_type", kwargs={"blog_id": self.blog.id}),
            data={"user_type": "coach"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Unable to generate the next question right now: invalid webhook payload",
        )
        self.assertFalse(AiGenerated.objects.exists())
