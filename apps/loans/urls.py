# apps/loans/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoanViewSet, 
    LoanRequestViewSet, 
    LoanSettingsViewSet,
    ECORETSettingsViewSet,
    ECORETBankAccountViewSet
)

router = DefaultRouter()
router.register(r'loans', LoanViewSet, basename='loan')
router.register(r'loan-requests', LoanRequestViewSet, basename='loan-request')
router.register(r'loan-settings', LoanSettingsViewSet, basename='loan-settings')
router.register(r'ecoret-settings', ECORETSettingsViewSet, basename='ecoret-settings')
router.register(r'ecoret-accounts', ECORETBankAccountViewSet, basename='ecoret-account')

urlpatterns = [
    path('', include(router.urls)),
]