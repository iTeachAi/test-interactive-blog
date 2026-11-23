import codecs
import re

from django import forms

from .models import BlogPost


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
