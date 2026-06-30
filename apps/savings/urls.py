from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SavingViewSet, SavingGoalViewSet

router = DefaultRouter()
router.register(r'savings', SavingViewSet, basename='saving')
router.register(r'saving-goals', SavingGoalViewSet, basename='saving-goal')

urlpatterns = [
    path('', include(router.urls)),
]