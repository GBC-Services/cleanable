from django.urls import path
from . import views


urlpatterns = [
    path('', views.Homepage.as_view(), name='homepage'),
    path('terms-of-use', views.TermsOfUseView.as_view(), name='terms_of_use'),
    path('privacy-policy', views.PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('accounts/signup', views.CustomSignUpView.as_view(), name='account_signup'),
    path('accounts/signup/<role>', views.CleanerSignUpView.as_view(), name='cleaner_signup'),

    path('profile-update', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('verification', views.VerificationsView.as_view(), name='verification'),
    path('upload-document/<uuid>', views.UploadDocumentView.as_view(), name='upload_document'),
    path('verification-document-action/<uuid>/<str:action>', views.VerificationDocumentActionView.as_view(),
         name='verification_document_action'),
]