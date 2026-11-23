def normalize_lesson(data):
    """Adapt the flat n8n lesson schema to the article renderer's structure."""
    if 'post' in data or 'schema_version' not in data:
        return data

    version = data['schema_version']
    if type(version) is not int or version != 1:
        raise ValueError('The webhook must return a supported lesson schema version.')

    topics = data.get('topics')
    if not isinstance(topics, dict):
        raise ValueError('Expected a topics object in the webhook output.')
    new_topics = topics.get('new_topics', [])
    if not isinstance(new_topics, list):
        raise ValueError('Expected topics.new_topics to be a list.')

    visuals = data.get('visuals', [])
    if not isinstance(visuals, list) or any(not isinstance(visual, dict) for visual in visuals):
        raise ValueError('Expected visuals to be a list of objects.')
    article_visuals = []
    visuals_by_section = {}
    for index, visual in enumerate(visuals):
        key = f'visual-{index}'
        article_visuals.append({
            **visual,
            'key': key,
            'alt_text_draft': visual.get('alt_text', ''),
        })
        section_id = visual.get('after_section_id')
        if isinstance(section_id, str):
            visuals_by_section.setdefault(section_id, []).append(key)

    sections = data.get('sections')
    if isinstance(sections, list):
        sections = [
            {**section, 'visual_keys': visuals_by_section.get(section['id'], [])}
            if isinstance(section, dict) and isinstance(section.get('id'), str)
            else section
            for section in sections
        ]

    return {
        **data,
        'schema_version': '1.0',
        'status': data.get('status', 'draft'),
        'classification': {'primary_topic_key': topics.get('primary_id')},
        'topic_mentions': [
            {**topic, 'key': topic.get('id')} for topic in new_topics if isinstance(topic, dict)
        ],
        'post': {
            'title': data.get('title'),
            'excerpt': data.get('excerpt'),
            'opening': data.get('opening', ''),
            'sections': sections,
            'closing_takeaway': data.get('closing', ''),
        },
        'visuals': article_visuals,
    }


def lesson_body(post):
    paragraphs = [post.get('opening', '')]
    for section in post['sections']:
        paragraphs.extend([section['heading'], *section['paragraphs']])
    paragraphs.extend([post.get('closing_takeaway', ''), post.get('reader_action', '')])
    return '\n\n'.join(filter(None, paragraphs))


def lesson_fields(data):
    post = data.get('post')
    classification = data.get('classification')
    source = data.get('source', {})
    if not all(isinstance(item, dict) for item in (post, classification, source)):
        raise ValueError('Expected post, classification, and source objects.')

    sections = post.get('sections')
    if not isinstance(sections, list) or any(
        not isinstance(section, dict)
        or not isinstance(section.get('heading'), str)
        or not isinstance(section.get('paragraphs'), list)
        or any(not isinstance(paragraph, str) for paragraph in section['paragraphs'])
        for section in sections
    ):
        raise ValueError('Expected post sections with headings and paragraphs.')

    for key in ('opening', 'closing_takeaway', 'reader_action'):
        if not isinstance(post.get(key, ''), str):
            raise ValueError(f'Expected post.{key} to be text.')

    topic_key = classification.get('primary_topic_key')
    if not isinstance(topic_key, str) or not topic_key.strip():
        raise ValueError('Expected classification.primary_topic_key.')

    topics = data.get('topic_mentions', [])
    if not isinstance(topics, list):
        raise ValueError('Expected topic_mentions to be a list.')
    category = next(
        (topic['label'] for topic in topics if isinstance(topic, dict)
         and topic.get('key') == topic_key and isinstance(topic.get('label'), str)
         and 0 < len(topic['label'].strip()) <= 50),
        topic_key.replace('-', ' ').replace('_', ' ').capitalize(),
    )
    return {
        'title': post.get('title', ''),
        'category': category,
        'summary': post.get('excerpt') or '',
        'author': (source.get('author_id') or '').replace('-', ' ').title()
        if isinstance(source.get('author_id'), str) else '',
        'body': lesson_body(post),
    }
