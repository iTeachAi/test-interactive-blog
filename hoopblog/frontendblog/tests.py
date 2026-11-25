from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from backend.models import Audience, BlogPost, ConsultationRequest, CourtTerm, VideoLesson


class PublicSiteTests(TestCase):
    def article(self, title, **kwargs):
        return BlogPost.objects.create(title=title, category='Decision-making', body='Read the defender.', **kwargs)

    def test_home_links_to_every_service(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Understand the game.')
        paths = [
            reverse('stat-analyzer'), reverse('consultation'), reverse('court-lingo'),
            reverse('video-lessons'),
            *(reverse('audience-blog', args=[role]) for role in Audience.Role.values),
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertContains(response, f'href="{path}"')
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_one_article_in_two_audiences_and_legacy_url(self):
        post = self.article('What Plus-Minus Can Tell You')
        post.audiences.set(['coach', 'parent'])
        for role in ('coach', 'parent'):
            response = self.client.get(reverse('audience-blog', args=[role]))
            self.assertContains(response, f'href="{post.get_absolute_url()}"')
        self.assertContains(self.client.get(post.get_absolute_url()), 'Want help teaching this concept to your team?')
        self.assertContains(self.client.get(f'/posts/{post.pk}/'), post.title)

        post.audiences.set(['player'])
        self.assertNotContains(self.client.get('/blog/coach/'), post.title)
        self.assertContains(self.client.get('/blog/player/'), post.title)

    def test_private_articles_stay_out_of_lists_detail_and_related_resources(self):
        term = CourtTerm.objects.get(slug='ice-the-ball-screen')
        video = VideoLesson.objects.create(title='Defending a side screen', topic='Defense', objective='Force baseline.',
                                           source_url='https://example.com/defense')
        video.audiences.add('coach')
        video.terms.add(term)
        for post in (
            self.article('Private draft', status=BlogPost.Status.DRAFT),
            self.article('Upcoming post', date=timezone.localdate() + timedelta(days=1)),
        ):
            post.audiences.add('coach')
            term.articles.add(post)
            video.articles.add(post)
            for path in ('/', '/blog/', '/blog/coach/', '/court-lingo/ice-the-ball-screen/', '/video-lessons/'):
                self.assertNotContains(self.client.get(path), post.title)
            for path in (post.get_absolute_url(), f'/posts/{post.pk}/'):
                self.assertEqual(self.client.get(path).status_code, 404)
        self.assertContains(self.client.get('/video-lessons/', {'topic': 'Defense', 'audience': 'coach'}), video.title)
        self.assertNotContains(self.client.get('/video-lessons/', {'audience': 'parent'}), video.title)

    def test_court_lingo_alias_and_related_lesson(self):
        self.assertContains(self.client.get('/court-lingo/', {'q': 'down coverage'}), 'Ice the ball screen')
        detail = self.client.get(reverse('court-term', args=['ice-the-ball-screen']))
        self.assertContains(detail, 'What it looks like on the court')
        self.assertContains(detail, '/posts/how-to-ice-a-side-ball-screen/')

    def test_consultation_validation_and_confirmation(self):
        self.client.post('/consultation/', {'email': 'invalid'})
        self.assertFalse(ConsultationRequest.objects.exists())
        response = self.client.post('/consultation/', {
            'name': 'Test Coach', 'email': 'coach@example.com', 'role': 'coach',
            'question': 'How should I teach ball-screen defense?',
        }, follow=True)
        self.assertRedirects(response, '/consultation/received/')
        self.assertContains(response, 'We received your request.')
        self.assertEqual(ConsultationRequest.objects.get().email, 'coach@example.com')

    @override_settings(N8N_TEST_WEBHOOK_URL=None)
    def test_stat_sheet_analysis(self):
        sheet = SimpleUploadedFile(
            'sample.csv',
            b'player_name,team,Points,AST,Turnovers,2PM,2PA,3PM,3PA\nAvery,Home,13.0,4,2,2,4,3,6\n',
        )
        response = self.client.post('/stat-sheet-analyzer/', {'sheet': sheet, 'statsheet_type': 'game', 'focus_team': 'home'})
        self.assertContains(response, '65.0%')
        self.assertContains(response, 'What needs more context')
        self.assertContains(response, 'Want help turning these numbers into a development plan?')

        invalid = SimpleUploadedFile('invalid.csv', b'player_name,Points\nAvery,not-a-number\n')
        response = self.client.post('/stat-sheet-analyzer/', {'sheet': invalid, 'statsheet_type': 'game', 'focus_team': 'home'})
        self.assertContains(response, 'Row 2 has an invalid value')
        self.assertNotContains(response, 'What the numbers show')

    @override_settings(N8N_TEST_WEBHOOK_URL='https://example.com/test')
    def test_analyzer_sends_game_focus_and_omits_it_for_team_statsheets(self):
        game_csv = 'Player,Points\r\nAvery,14\r\n'
        team_csv = 'Team,Points\nFalcons,75\n'
        with patch('frontendblog.views.request_webhook_output', return_value={}) as webhook:
            game = self.client.post('/stat-sheet-analyzer/', {
                'sheet': SimpleUploadedFile('game.csv', game_csv.encode()),
                'statsheet_type': 'game',
                'focus_team': 'away',
            })
            webhook.assert_called_once_with('https://example.com/test', {
                'task': 'statsheet', 'csv': game_csv, 'statsheet_type': 'game', 'focus_team': 'away',
            })
            self.assertContains(game, 'What the numbers show')

            webhook.reset_mock()
            team = self.client.post('/stat-sheet-analyzer/', {
                'sheet': SimpleUploadedFile('team.csv', team_csv.encode()),
                'statsheet_type': 'team',
                'focus_team': 'home',
            })
            webhook.assert_called_once_with('https://example.com/test', {
                'task': 'statsheet', 'csv': team_csv, 'statsheet_type': 'team',
            })
            self.assertContains(team, '75 · Falcons')

            webhook.reset_mock()
            missing_focus = self.client.post('/stat-sheet-analyzer/', {
                'sheet': SimpleUploadedFile('game.csv', game_csv.encode()), 'statsheet_type': 'game',
            })
            self.assertContains(missing_focus, 'Choose Home or Away for a game stat sheet.')
            self.client.post('/stat-sheet-analyzer/', {
                'sheet': SimpleUploadedFile('bad.csv', b'invalid'), 'statsheet_type': 'team',
            })
            webhook.assert_not_called()

    @override_settings(CONSULTATION_BOOKING_URL='https://example.com/book',
                       STAT_SHEET_ANALYZER_URL='https://example.com/analyzer')
    def test_configured_external_services(self):
        self.assertRedirects(self.client.get('/consultation/'), 'https://example.com/book', fetch_redirect_response=False)
        self.assertContains(self.client.get('/stat-sheet-analyzer/'), 'href="https://example.com/analyzer"')
        self.assertContains(self.client.get('/stat-sheet-analyzer/results/'), 'Want help turning these numbers')


class EditorialWorkflowTests(TestCase):
    def test_structured_webhook_audiences_are_saved(self):
        self.client.force_login(get_user_model().objects.create_superuser(username='editor'))
        output = {
            'schema_version': 1,
            'title': 'Practice spacing',
            'category': 'Team offense',
            'topics': {'primary_id': 'spacing', 'new_topics': [{'id': 'decision-making', 'label': 'Decision-making'}]},
            'classification': {'primary_audience': 'Coach', 'secondary_audiences': ['Parents']},
            'sections': [{'heading': 'Start in the corner', 'paragraphs': ['Spread the floor.']}],
            'status': 'published',
        }
        with override_settings(N8N_TEST_WEBHOOK_URL='https://example.com/webhook'):
            with patch('backend.webhook.request_webhook_output', return_value=output):
                response = self.client.post('/editor/new/', {'body': 'Source material'})
        self.assertRedirects(response, '/editor/')
        post = BlogPost.objects.get(title='Practice spacing')
        self.assertSetEqual(set(post.audiences.values_list('pk', flat=True)), {'coach', 'parent'})
        self.assertEqual(post.topics, 'Decision-making')
        self.assertEqual(post.category, 'Team offense')
        self.assertContains(self.client.get('/editor/'), 'Team offense')
        self.assertContains(self.client.get('/blog/parent/'), post.get_absolute_url())

    def test_editor_services_require_staff_access(self):
        for path in ('/editor/stat-analyzer/', '/editor/court-lingo/', '/editor/court-lingo/new/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('/admin/login/'))
        self.client.force_login(get_user_model().objects.create_user(username='visitor'))
        self.assertEqual(self.client.get('/editor/stat-analyzer/').status_code, 403)
        self.assertEqual(self.client.get('/editor/court-lingo/new/').status_code, 403)

    @override_settings(N8N_TEST_WEBHOOK_URL="https://example.com/test")
    def test_editor_csv_analysis(self):
        self.client.force_login(get_user_model().objects.create_user(username='staff', is_staff=True))
        csv_text = 'Player,Points,Assists,Turnovers\nAvery,14,5,2\n'
        sheet = SimpleUploadedFile('game.csv', csv_text.encode('utf-8'))
        with patch('frontendblog.views.request_webhook_output', return_value={}) as webhook:
            response = self.client.post('/editor/stat-analyzer/', {
                'sheet': sheet, 'statsheet_type': 'game', 'focus_team': 'home',
            })
        webhook.assert_called_once_with('https://example.com/test', {
            'task': 'statsheet', 'csv': csv_text, 'statsheet_type': 'game', 'focus_team': 'home',
        })
        self.assertContains(response, 'What the numbers show')
        self.assertContains(response, 'Avery')
        self.assertContains(response, 'What to look for next')
        self.assertContains(response, '14 · Avery')

    @override_settings(STAT_SHEET_IMAGE_WEBHOOK_URL='https://example.com/extract')
    def test_editor_image_analysis_uses_extracted_stats(self):
        self.client.force_login(get_user_model().objects.create_user(username='staff', is_staff=True))
        with patch('frontendblog.editor_stats.request_webhook_output',
                   return_value={'csv': 'player_name,points\nAvery,14\n'}) as extract:
            invalid = SimpleUploadedFile('bad.png', b'wrong file')
            self.assertContains(self.client.post('/editor/stat-analyzer/', {'sheet': invalid, 'statsheet_type': 'game', 'focus_team': 'home'}), 'file contents do not match')
            extract.assert_not_called()
            image = SimpleUploadedFile('game.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
            response = self.client.post('/editor/stat-analyzer/', {'sheet': image, 'statsheet_type': 'game', 'focus_team': 'home'})
        extract.assert_called_once_with('https://example.com/extract', {
            'task': 'extract_stat_sheet', 'mime_type': 'image/png', 'image_base64': 'iVBORw0KGgo=',
            'statsheet_type': 'game', 'focus_team': 'home',
        })
        self.assertContains(response, 'Avery')
        self.assertContains(response, 'What the numbers show')

    def test_editor_can_publish_and_update_a_definition(self):
        self.client.force_login(get_user_model().objects.create_superuser(username='editor'))
        response = self.client.post('/editor/court-lingo/new/', {
            'name': 'Short roll', 'meaning': 'Roll into the middle of the floor after screening.',
        })
        self.assertRedirects(response, '/editor/court-lingo/')
        term = CourtTerm.objects.get(slug='short-roll')
        response = self.client.get('/court-lingo/short-roll/')
        self.assertContains(response, term.meaning)
        self.assertNotContains(response, 'When you’ll hear it')
        duplicate = self.client.post('/editor/court-lingo/new/', {'name': 'Short Roll', 'meaning': 'Duplicate.'})
        self.assertContains(duplicate, 'An entry for this term already exists.')
        response = self.client.post(f'/editor/court-lingo/{term.pk}/edit/', {
            'name': 'Short roll pass', 'meaning': term.meaning, 'aliases': 'Pocket pass option',
        })
        self.assertRedirects(response, '/editor/court-lingo/')
        self.assertContains(self.client.get('/court-lingo/short-roll/'), 'Short roll pass')


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class CourtLingoPDFTests(TestCase):
    pdf = b'%PDF-1.4\n%%EOF\n'

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser(username='pdf-editor'))

    def test_publish_term_with_pdf_and_public_viewer(self):
        response = self.client.post('/editor/court-lingo/new/', {
            'name': 'Spain pick-and-roll',
            'pdf': SimpleUploadedFile('spain.pdf', self.pdf, content_type='application/pdf'),
        })
        self.assertRedirects(response, '/editor/court-lingo/')
        term = CourtTerm.objects.get(slug='spain-pick-and-roll')
        edit_url = reverse('editor-term-update', args=[term.pk])
        self.assertContains(self.client.get(edit_url), 'Remove current PDF')

        self.client.logout()
        url = '/court-lingo/spain-pick-and-roll/pdf/'
        page = self.client.get('/court-lingo/spain-pick-and-roll/')
        self.assertContains(page, f'<iframe src="{url}"')
        self.assertContains(page, 'Open PDF in new tab')
        self.assertContains(page, 'pdf-fullscreen')
        document = self.client.get(url)
        self.assertEqual(document.headers['Content-Type'], 'application/pdf')
        self.assertEqual(document.headers['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(document.headers['Content-Disposition'], 'inline; filename="spain-pick-and-roll.pdf"')
        self.assertEqual(b''.join(document.streaming_content), self.pdf)

    def test_invalid_pdf_and_missing_content_are_rejected(self):
        response = self.client.post('/editor/court-lingo/new/', {
            'name': 'Broken document', 'pdf': SimpleUploadedFile('broken.pdf', b'Plain text'),
        })
        self.assertContains(response, 'Choose a valid PDF document.')
        response = self.client.post('/editor/court-lingo/new/', {'name': 'Empty term'})
        self.assertContains(response, 'Add a definition or upload a PDF.')
        self.assertFalse(CourtTerm.objects.filter(name__in=['Broken document', 'Empty term']).exists())

    def test_remove_pdf_from_term_with_definition(self):
        term = CourtTerm.objects.get(slug='ice-the-ball-screen')
        term.pdf.save('ice.pdf', SimpleUploadedFile('ice.pdf', self.pdf))
        response = self.client.post(reverse('editor-term-update', args=[term.pk]), {
            'name': term.name, 'meaning': term.meaning, 'pdf-clear': 'on',
        })
        self.assertRedirects(response, '/editor/court-lingo/')
        self.assertEqual(self.client.get('/court-lingo/ice-the-ball-screen/pdf/').status_code, 404)
        self.assertContains(self.client.get('/court-lingo/ice-the-ball-screen/'), term.meaning)
