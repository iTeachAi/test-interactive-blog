import json
import ssl
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from .audiences import audience_slugs
from .forms import BlogPostForm
from .lessons import lesson_fields, normalize_lesson
from .models import BlogPost


class BlogWebhookError(Exception):
    pass


def webhook_tls_context():
    context = ssl.create_default_context()
    system_bundle = Path('/etc/ssl/cert.pem')
    if not context.get_ca_certs() and system_bundle.is_file():
        context.load_verify_locations(cafile=str(system_bundle))
    return context


def request_webhook_output(webhook_url, submission):
    try:
        request = Request(
            webhook_url,
            data=json.dumps(submission).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            method='POST',
        )
        with urlopen(request, timeout=180, context=webhook_tls_context()) as response:
            max_bytes = 8 * 1024 * 1024
            payload = response.read(max_bytes + 1)
    except HTTPError as error:
        with error:
            if error.code == 404 and '/webhook-test/' in urlsplit(webhook_url).path:
                raise BlogWebhookError(
                    'n8n returned HTTP 404. Confirm the Test URL and POST method, '
                    'then click Listen for test event in n8n and submit again.'
                ) from error
        raise BlogWebhookError(f'The webhook returned HTTP {error.code}.') from error
    except URLError as error:
        if isinstance(error.reason, ssl.SSLCertVerificationError):
            raise BlogWebhookError('Django could not verify the webhook’s TLS certificate.') from error
        if isinstance(error.reason, TimeoutError):
            raise BlogWebhookError('Django timed out waiting for the webhook.') from error
        raise BlogWebhookError('Django could not connect to the webhook.') from error
    except TimeoutError as error:
        raise BlogWebhookError('Django timed out waiting for the webhook.') from error
    except (OSError, HTTPException, ValueError) as error:
        raise BlogWebhookError('The webhook could not process the post. Try again.') from error

    try:
        if len(payload) > max_bytes:
            raise ValueError('Response is too large')
        data = json.loads(payload)
        json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, RecursionError) as error:
        raise BlogWebhookError('The webhook did not return a usable JSON response.') from error

    if isinstance(data, list):
        if len(data) != 1:
            raise BlogWebhookError('Expected one result from the webhook.')
        data = data[0]
    if isinstance(data, dict) and 'output' in data:
        data = data['output']
    if not isinstance(data, dict):
        raise BlogWebhookError('The webhook must return a JSON object, optionally wrapped in an output field.')
    return data


def generate_blog_image(post):
    webhook_url = settings.N8N_TEST_WEBHOOK_URL
    if not webhook_url:
        raise BlogWebhookError('Set a blog webhook URL before generating an image.')

    audience = post.lesson.get('audience')
    if not audience:
        audience = post.lesson.get('classification', {}).get('primary_audience')
    data = request_webhook_output(webhook_url, {
        'task': 'image',
        'title': post.title,
        'excerpt': post.summary,
        'audience': audience or '',
    })
    image_url = data.get('secure_url') or data.get('image_url')
    invalid_url = 'The image webhook must return a valid HTTPS secure_url or image_url.'
    field = BlogPost._meta.get_field('image_url')
    if not isinstance(image_url, str) or not image_url.strip() or len(image_url.strip()) > field.max_length:
        raise BlogWebhookError(invalid_url)
    image_url = image_url.strip()
    try:
        URLValidator(schemes=['https'])(image_url)
    except ValidationError as error:
        raise BlogWebhookError(invalid_url) from error
    image_alt = data.get('image_alt', '')
    if not isinstance(image_alt, str):
        raise BlogWebhookError('The image webhook must return image_alt as text when provided.')
    return {
        'image_url': image_url,
        'image_alt': image_alt.strip()[:BlogPost._meta.get_field('image_alt').max_length],
    }


def process_blog_post(body, *, submission_type):
    webhook_url = settings.N8N_TEST_WEBHOOK_URL
    if not webhook_url:
        raise BlogWebhookError('Set a blog webhook URL before sending a post.')
    data = request_webhook_output(webhook_url, {'body': body, 'type': submission_type})

    structured = 'schema_version' in data or 'post' in data
    if structured:
        try:
            data = normalize_lesson(data)
            fields = lesson_fields(data)
            fields['category'] = data.get('category', data['classification'].get('category', fields['category']))
        except ValueError as error:
            raise BlogWebhookError(str(error)) from error
        if data.get('schema_version') != '1.0':
            raise BlogWebhookError('The webhook must return lesson schema version 1.0.')
        status = data.get('status')
        if status not in BlogPost.Status.values:
            raise BlogWebhookError('The lesson status must be draft, approved, or published.')
    else:
        fields = {name: data.get(name, '') for name in BlogPostForm.Meta.fields}
    if any(not isinstance(value, str) for value in fields.values()):
        raise BlogWebhookError('The webhook must return blog fields as text.')

    post_form = BlogPostForm(fields)
    if not post_form.is_valid():
        invalid_fields = ', '.join(post_form.errors)
        raise BlogWebhookError(f'The webhook returned invalid fields ({invalid_fields}).')

    result = dict(post_form.cleaned_data)
    audiences = audience_slugs(data) or audience_slugs({'audience': result['category']})
    if audiences:
        result['audiences'] = audiences
    if structured:
        result.update(status=status, lesson=data)
        topics = [
            topic.get('label') or topic.get('key')
            for topic in data.get('topic_mentions', []) if isinstance(topic, dict)
        ]
        labels = [topic for topic in topics if isinstance(topic, str) and topic != result['category']]
        result['topics'] = ', '.join(dict.fromkeys(labels))[:500]
    return result
