from django.urls import path
from .views import (
    InitiatePayoutView,
    InitiatePaymentView,
    TransactionStatusView,
    TransactionHistoryView,
    BalanceView,
    paychangu_webhook
)

urlpatterns = [
    # Mobile money operations
    path('payout/', InitiatePayoutView.as_view(), name='payout'),
    path('payment/', InitiatePaymentView.as_view(), name='payment'),
    
    # Transaction status
    path('status/', TransactionStatusView.as_view(), name='transaction-status'),
    path('history/', TransactionHistoryView.as_view(), name='transaction-history'),
    
    # Balance check
    path('balance/', BalanceView.as_view(), name='balance'),
    
    # Webhook for PayChangu callbacks
    path('webhook/', paychangu_webhook, name='paychangu-webhook'),
]