from django.urls import path
from . import views

urlpatterns = [
    path('badges/', views.BadgeCatalogView.as_view(), name='badge_catalog'),
    path('my-progress/', views.MyProgressView.as_view(), name='my_progress'),
    path('students/<int:student_id>/progress/', views.StudentProgressView.as_view(), name='student_progress'),
]
