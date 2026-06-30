from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoanViewSet, LoanRequestViewSet, LoanSettingsViewSet

router = DefaultRouter()
router.register(r'loans', LoanViewSet, basename='loan')
router.register(r'loan-requests', LoanRequestViewSet, basename='loan-request')
router.register(r'loan-settings', LoanSettingsViewSet, basename='loan-settings')

urlpatterns = [
    path('', include(router.urls)),
]