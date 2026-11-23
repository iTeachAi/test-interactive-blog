
from django.contrib import admin
from django.urls import path, include
from .views import (
    HomeView, 
    RegisterView,
    ChooseBlogView,
    SelectUserTypeView, 
    UserAnswerView, 
    BlogAnswersView,
    PersonalizedBlogDetailView,
)


urlpatterns = [
    path('', HomeView.as_view(), name="home"),
    path('register/', RegisterView.as_view(), name='register'),
    path('choose/<int:blog_id>/', ChooseBlogView.as_view(), name='choose_blog'),
    path('type/<int:blog_id>/', SelectUserTypeView.as_view(), name="user_type"),
    path('question/<int:pk>/', UserAnswerView.as_view(), name="user_question"),
    path('answers/<int:blog_id>/', BlogAnswersView.as_view(), name="blog_answers"),
    path('blog/<int:pk>/', PersonalizedBlogDetailView.as_view(), name="personalized_blog"),
]
