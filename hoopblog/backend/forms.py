import codecs
import re

from django import forms
from django.utils.text import slugify

from .models import BlogPost, ConsultationRequest, CourtTerm


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ('title', 'category', 'author', 'summary', 'body')


class BlogPostImportForm(BlogPostForm):
    body = forms.CharField(widget=forms.Textarea, required=False)
    source_file = forms.FileField(
        required=False,
        label='Or upload a text file',
        help_text='Plain text up to 1 MiB. Any file extension is accepted.',
    )

    def clean(self):
        cleaned_data = super().clean()
        source = cleaned_data.get('source_file')
        body = cleaned_data.get('body')

        if source is None:
            if not body and 'source_file' in cleaned_data:
                self.add_error('body', 'Enter the post body or upload a file.')
            return cleaned_data

        if body:
            self.add_error('source_file', 'Clear the Body field before importing a file.')
            return cleaned_data

        if source.size > 1024 * 1024:
            self.add_error('source_file', 'Upload a text file no larger than 1 MiB.')
            return cleaned_data

        data = source.read()
        encoding = 'utf-8-sig'
        if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            encoding = 'utf-32'
        elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            encoding = 'utf-16'

        try:
            body = data.decode(encoding).strip()
        except UnicodeDecodeError:
            if encoding == 'utf-8-sig' and not data.startswith(codecs.BOM_UTF8):
                body = data.decode('cp1252', errors='replace').strip()
                if '\ufffd' in body:
                    body = ''
            else:
                body = ''

        if not body or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', body):
            self.add_error('source_file', 'Upload a file containing plain text.')
            return cleaned_data

        cleaned_data['body'] = body
        return cleaned_data


class NewBlogPostForm(BlogPostImportForm):
    class Meta(BlogPostImportForm.Meta):
        fields = ('body',)


class ConsultationRequestForm(forms.ModelForm):
    class Meta:
        model = ConsultationRequest
        fields = ('name', 'email', 'role', 'question')
        labels = {'question': 'What basketball question would you like to work through?'}
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'question': forms.Textarea(attrs={'rows': 5}),
        }

class CourtTermPDFInput(forms.ClearableFileInput):
    template_name = 'frontendblog/editor/pdf_input.html'

    def __init__(self, attrs=None):
        super().__init__({'accept': '.pdf,application/pdf', **(attrs or {})})


class CourtTermEditorForm(forms.ModelForm):
    class Meta:
        model = CourtTerm
        fields = ('name', 'pdf', 'meaning', 'aliases', 'when_to_use', 'on_court', 'articles')
        labels = {'name': 'Word or phrase', 'meaning': 'Definition or concept', 'articles': 'Related articles'}
        widgets = {
            'pdf': CourtTermPDFInput,
            'meaning': forms.Textarea(attrs={'rows': 5}),
            'when_to_use': forms.Textarea(attrs={'rows': 3}),
            'on_court': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_name(self):
        name = self.cleaned_data['name']
        slug = slugify(name)[:50].rstrip('-')
        if not slug:
            raise forms.ValidationError('Enter a term with at least one letter or number.')
        terms = CourtTerm.objects.exclude(pk=self.instance.pk)
        if terms.filter(name__iexact=name).exists() or (
            not self.instance.pk and terms.filter(slug=slug).exists()
        ):
            raise forms.ValidationError('An entry for this term already exists.')
        if not self.instance.pk:
            self.instance.slug = slug
        return name
