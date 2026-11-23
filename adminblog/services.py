from django.conf import settings

from pathlib import Path
from urllib.parse import urlparse
import requests
from django.core.files.base import ContentFile

def attach_blog_image(blog, image_url):
    response = requests.get(image_url, timeout=120)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ValueError("The webhook image URL did not return an image")

    extension = Path(urlparse(image_url).path).suffix or ".jpg"
    filename = f"blog-{blog.pk}{extension}"

    blog.image.save(
        filename,
        ContentFile(response.content),
        save=True,
    )
def generate_topics(lesson_description):
    data = {
        "task": "topics",
        "lesson": lesson_description,
    }

    response = requests.post(
        settings.N8N_WEBHOOK_URL,
        data=data,
        timeout=120,
    )
    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list) or not payload:
        raise ValueError("The webhook returned an invalid response.")

    first_item = payload[0]

    if not isinstance(first_item, dict):
        raise ValueError("The first webhook result was not an object.")

    output = first_item.get("output")

    if not isinstance(output, dict):
        raise ValueError("The webhook output was not a valid object.")

    lesson_focus = output.get("lesson_focus", "")
    blog_options = output.get("blog_options")

    if not isinstance(blog_options, list) or not blog_options:
        raise ValueError("The webhook did not return any blog options.")

    normalized_topics = []

    for index, option in enumerate(blog_options):
        option_number = index + 1

        if not isinstance(option, dict):
            raise ValueError(
                f"Blog option {option_number} was not an object."
            )

        title = option.get("title", "")
        questions = option.get("questions")

        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"Blog option {option_number} did not contain a title."
            )

        if not isinstance(questions, list):
            raise ValueError(
                f"Blog option {option_number} did not contain a question list."
            )

        if len(questions) < 5:
            raise ValueError(
                f"Blog option {option_number} contained fewer than five questions."
            )

        first_five_questions = questions[:5]

        if not all(
            isinstance(question, str) and question.strip()
            for question in first_five_questions
        ):
            raise ValueError(
                f"Blog option {option_number} contained an invalid question."
            )

        normalized_topics.append(
            {
                "topic": title.strip(),
                "principle": lesson_focus,
                "questions": [
                    question.strip()
                    for question in first_five_questions
                ],
            }
        )

    return normalized_topics


def generate_blog(blog_questions):
    data = {
        "task": "generate_blog",
        "topic": blog_questions.generated_topic,
        "principle": blog_questions.principle,
        "question1": blog_questions.question1,
        "answer1": blog_questions.answer1,
        "question2": blog_questions.question2,
        "answer2": blog_questions.answer2,
        "question3": blog_questions.question3,
        "answer3": blog_questions.answer3,
        "question4": blog_questions.question4,
        "answer4": blog_questions.answer4,
        "question5": blog_questions.question5,
        "answer5": blog_questions.answer5,
    }

    response = requests.post(
        settings.N8N_WEBHOOK_URL,
        data=data,
        timeout=120,
    )
    response.raise_for_status()

    payload = response.json()

    # n8n may wrap its result in one or more lists or "output" objects.
    while True:
        if isinstance(payload, list):
            if not payload:
                raise ValueError(
                    "The blog webhook returned an empty list."
                )
            payload = payload[0]
            continue

        if isinstance(payload, dict) and "output" in payload:
            payload = payload["output"]
            continue

        break

    if not isinstance(payload, dict):
        raise ValueError(
            "The blog webhook did not return a valid object."
        )

    if not payload.get("content"):
        raise ValueError(
            "The blog webhook response did not contain blog content."
        )

    return payload
