from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessTypeChoicesView, GroupViewSet

router = DefaultRouter()
router.register(r'groups', GroupViewSet, basename='group')

urlpatterns = [
    path('', include(router.urls)),
    path('business-types/', BusinessTypeChoicesView.as_view(), name='business-type-choices'),
]