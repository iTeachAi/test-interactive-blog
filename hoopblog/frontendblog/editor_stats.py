from base64 import b64encode
from pathlib import Path

from django import forms
from django.conf import settings
from django.views.generic import FormView

from backend.webhook import BlogWebhookError, request_webhook_output

from .editor import BlogEditorAccessMixin
from .stat_sheet import analyze_rows, stat_highlights
from .views import StatSheetForm


class EditorStatSheetForm(StatSheetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.STAT_SHEET_IMAGE_WEBHOOK_URL:
            self.fields['sheet'].label = 'Upload a stat sheet'
            self.fields['sheet'].widget.attrs['accept'] += ',.png,.jpg,.jpeg,image/png,image/jpeg'

    def clean_sheet(self):
        sheet = self.cleaned_data['sheet']
        extension = Path(sheet.name).suffix.lower()
        if extension == '.csv':
            return super().clean_sheet()
        if extension not in ('.png', '.jpg', '.jpeg'):
            raise forms.ValidationError('Choose a CSV, PNG, or JPEG stat sheet.')
        if not settings.STAT_SHEET_IMAGE_WEBHOOK_URL:
            raise forms.ValidationError('Image analysis is unavailable. Choose a CSV stat sheet.')
        if sheet.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Upload an image no larger than 5 MiB.')
        data = sheet.read()
        mime = 'image/png' if extension == '.png' else 'image/jpeg'
        signature = b'\x89PNG\r\n\x1a\n' if extension == '.png' else b'\xff\xd8\xff'
        if not data.startswith(signature):
            raise forms.ValidationError('The file contents do not match the image format.')
        if self.errors:
            return None
        try:
            output = request_webhook_output(settings.STAT_SHEET_IMAGE_WEBHOOK_URL, {
                'task': 'extract_stat_sheet',
                'mime_type': mime,
                'image_base64': b64encode(data).decode('ascii'),
                **self.statsheet_metadata(),
            })
        except BlogWebhookError as error:
            raise forms.ValidationError('The image extraction service could not read this stat sheet. Try again or use a CSV.') from error
        csv_text = output.get('csv')
        if not isinstance(csv_text, str) or len(csv_text.encode('utf-8')) > 256 * 1024:
            raise forms.ValidationError('The image extraction service did not return a usable CSV.')
        try:
            return analyze_rows(csv_text.lstrip('\ufeff'), allow_team_rows=self.cleaned_data['statsheet_type'] == 'team')
        except ValueError as error:
            raise forms.ValidationError(str(error)) from error


class EditorStatSheetView(BlogEditorAccessMixin, FormView):
    form_class = EditorStatSheetForm
    template_name = 'frontendblog/editor/stat_sheet.html'

    def get_context_data(self, **kwargs):
        return super().get_context_data(image_enabled=bool(settings.STAT_SHEET_IMAGE_WEBHOOK_URL), **kwargs)

    def form_valid(self, form):
        players = form.cleaned_data['sheet']
        return self.render_to_response(self.get_context_data(form=form, players=players, highlights=stat_highlights(players)))
