from django.urls import path
# from ussd.views import USSDView
from apps.ussd.views import USSDView

urlpatterns = [
    path('ussd/', USSDView.as_view(), name='ussd-handler'),
    # path('ussd-api/', USSDApiView.as_view(), name='ussd-api'),
]