# # apps/notifications/urls.py
# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views import NotificationViewSet, SendNotificationView

# router = DefaultRouter()
# router.register(r'notifications', NotificationViewSet, basename='notification')

# urlpatterns = [
#     path('', include(router.urls)),
#     path('send/', SendNotificationView.as_view(), name='send-notification'),
# ]
# apps/notifications/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationViewSet, 
    NotificationPreferenceViewSet, 
    NotificationQueueViewSet,
    SendNotificationView,
    TestNotificationView
)

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='preference')
router.register(r'queue', NotificationQueueViewSet, basename='queue')

urlpatterns = [
    # Custom endpoints with different paths
    path('test-endpoint/', TestNotificationView.as_view(), name='test-notification'),
    path('send-notification/', SendNotificationView.as_view(), name='send-notification'),
    # Router endpoints
    path('', include(router.urls)),
]