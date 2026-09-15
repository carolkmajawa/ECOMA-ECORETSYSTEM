from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView, RegisterView, LogoutView, ChangePasswordView,
    ForgotPasswordView, ResetPasswordView, UserProfileView,
    UserDeviceRegisterView, UserListView, UserActivityLogView,
    CheckAuthView, AdminUserUpdateView,AdminRequestView,
    AdminRequestDetailView,PendingAdminRequestsView,
)

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('check/', CheckAuthView.as_view(), name='check-auth'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('device/register/', UserDeviceRegisterView.as_view(), name='device-register'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<uuid:pk>/status/', AdminUserUpdateView.as_view(), name='admin-user-status'),
    path('activities/', UserActivityLogView.as_view(), name='user-activities'),
    path('admin-requests/', AdminRequestView.as_view(), name='admin-requests'),
    path('admin-requests/pending/', PendingAdminRequestsView.as_view(), name='admin-requests-pending'),
    path('admin-requests/<uuid:pk>/', AdminRequestDetailView.as_view(), name='admin-request-detail'),
]