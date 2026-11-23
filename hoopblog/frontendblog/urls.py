from django.urls import path

from .editor import BlogCreateView, BlogDeleteView, BlogEditorView, BlogGenerateImageView, BlogUpdateView
from .views import BlogDetailView, BlogHomeView

urlpatterns = [
    path('editor/', BlogEditorView.as_view(), name='blog-editor'),
    path('editor/new/', BlogCreateView.as_view(), name='blog-create'),
    path('editor/<int:pk>/edit/', BlogUpdateView.as_view(), name='blog-update'),
    path('editor/<int:pk>/image/', BlogGenerateImageView.as_view(), name='blog-generate-image'),
    path('editor/<int:pk>/delete/', BlogDeleteView.as_view(), name='blog-delete'),
    path('', BlogHomeView.as_view(), name='home'),
    path('posts/<int:pk>/', BlogDetailView.as_view(), name='blog-detail'),
]
