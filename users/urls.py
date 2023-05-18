from django.urls import include, path
from . import views


urlpatterns = [
    path('', views.Homepage.as_view(), name='homepage'),
    path('terms-of-use', views.TermsOfUseView.as_view(), name='terms_of_use'),
    path('privacy-policy', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
]