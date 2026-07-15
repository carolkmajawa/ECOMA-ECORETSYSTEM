from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceViewSet, MeetingViewSet, ParticipationTrackingViewSet, AttendanceCaseViewSet

router = DefaultRouter()
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'meetings', MeetingViewSet, basename='meeting')
router.register(r'participation', ParticipationTrackingViewSet, basename='participation')
router.register(r'attendance-cases', AttendanceCaseViewSet, basename='attendance-case')

urlpatterns = [
    path('', include(router.urls)),
]