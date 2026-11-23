import mimetypes
from django.conf import settings
import requests

def generate_question(user_type, blog_content):
    webhook_url = settings.N8N_WEBHOOK_URL

    data = {
        "task": "questionforuser",
        "type": user_type,
        "blog_content": blog_content,
    }
    if data:
        response = requests.post(
            webhook_url,
            data=data,
            timeout=120,
        )

    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, list) or not payload:
        raise ValueError("The webhook returned an invalid response")

    output = payload[0].get("output")

    if isinstance(output, dict):
        output = output.get("question")

    if isinstance(output, list):
        if not output:
            raise ValueError("The webhook response returned an empty question list.")
        output = output[0]

    if not isinstance(output, str):
        raise ValueError("The webhook response did not return a valid question.")

    return output.strip()


def generate_personalized_blog(blog_answer):
    data = {
        "task": "userblog",
        "user_type": blog_answer.session.user_type,
        "original_title": blog_answer.blog.name,
        "original_summary": blog_answer.blog.summary,
        "original_content": blog_answer.blog.content,
        "question": blog_answer.question,
        "answer": blog_answer.answer,
    }

    response = requests.post(
        settings.N8N_WEBHOOK_URL,
        data=data,
        timeout=120,
    )

    response.raise_for_status()
    payload = response.json()

    # Handle N8N response 
    while True:
        if isinstance(payload, list):
            if not payload:
                raise ValueError(
                    "The blog webhook returned a empty list."
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
            "The webhook response did not contain blog content."
        )
    return payload
