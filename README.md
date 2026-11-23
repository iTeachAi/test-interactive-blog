# Interactive Basketball Blog

A Django + n8n powered content platform that turns a short basketball lesson idea into a fully structured, publish-ready blog post through a guided, AI-assisted workflow.

## Overview

A user submits a short lesson description, and the platform sends it through an n8n automation workflow that generates candidate article topics. The user selects a topic, answers five guided follow-up questions to add depth and context, and the system then generates a complete blog post — title, category, summary, author, and full content — which is stored and displayed through Django.

## Features

- Guided, multi-step workflow from lesson idea to finished article
- AI-assisted topic generation via an n8n automation pipeline
- Five-question follow-up flow to strengthen article substance before generation
- Automatic structuring of title, category, summary, author, and content
- Django-powered storage, retrieval, and display (models, views, templates, ORM)
- Responsive, dashboard-style UI with custom styling
- Card-based layout for browsing generated articles

## Tech Stack

- **Backend:** Python, Django 6
- **Automation:** n8n (webhooks, AI-assisted generation)
- **Frontend:** Django templates, Bootstrap, Bootstrap Icons, custom CSS
- **Database:** SQLite (development)
- **Integration:** JSON over webhooks between Django and n8n

## Screenshots

| App Dashboard | Post Form |
|---|---|
| ![App Dashboard](screenshots/app-dashboard.jpg) | ![App Post Form](screenshots/app-post-form.jpg) |

| Blog Dashboard | Blog Topics |
|---|---|
| ![Blog Dashboard](screenshots/blog-dashboard.jpg) | ![Blog Topics](screenshots/blog-topics.jpg) |

| Blog Questions |
|---|
| ![Blog Questions](screenshots/blog-questions.jpg) |

> Place the corresponding image files in a `screenshots/` folder at the project root for these to render.

## Getting Started

```bash
# Clone the repository
git clone https://github.com/iTeachAi/Interactive-Basketball-Blog.git
cd Interactive-Basketball-Blog

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Run the development server
python manage.py runserver
```

The app also requires an n8n instance with the corresponding webhook workflow configured to handle topic generation, follow-up questions, and article generation.

## Project Structure

```
├── adminblog/       # Blog, Topic, and question models; admin-side content management
├── app/             # User-facing app, AI-generated session/answer/blog models
├── hoopcitylessons/ # Django project settings, URLs, WSGI/ASGI entry points
├── media/           # Uploaded blog images
├── manage.py
└── requirements.txt
```

## Roadmap

- Secure, signed webhooks between Django and n8n
- User authentication
- Image uploading and cloud storage
- AI-generated cover images
- PostgreSQL migration
- Blog editing, search, and filtering
- Analytics and generation history
- Improved error handling
- Content expansion (social posts, video scripts, lesson plans)

## Credits

Designed and developed by **MO**, with AI used as a coding partner for debugging, workflow planning, prompt development, and template design.

## License

- CC BY-NC-ND 
