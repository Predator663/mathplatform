from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('grade-levels', views.GradeLevelViewSet, basename='gradelevel')
router.register('classrooms', views.ClassroomViewSet, basename='classroom')
router.register('profiles', views.StudentProfileViewSet, basename='student')
router.register('parent-links', views.ParentStudentLinkViewSet, basename='parentlink')

urlpatterns = [
    path('', include(router.urls)),
]
