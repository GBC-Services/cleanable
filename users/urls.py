from django.urls import include, path
from . import views


urlpatterns = [
    path('', views.Homepage.as_view(), name='homepage'),
    path('terms-of-use', views.TermsOfUseView.as_view(), name='terms_of_use'),
    path('privacy-policy', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('accounts/signup/', views.CustomSignUpView.as_view(), name='account_signup'),
    path('accounts/signup/<role>', views.CleanerSignUpView.as_view(), name='cleaner_signup'),
]