from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from allauth.account.views import SignupView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from .forms import ProfileForm, UserVerificationDocumentForm
from .models import UserVerificationDocument
from apps.utils.mixins.access_mixins import GeneralAdminAccessMixin, CleanerAccessMixin
from django.contrib import messages


class Homepage(generic.TemplateView):
    public_homepage_name = "users/public_homepage.html"

    def dispatch(self, request, *args, **kwargs):
        dispatch = super().dispatch(request, *args, **kwargs)
        user = request.user
        if user.is_authenticated:
            if user.is_general_admin:
                return HttpResponseRedirect(reverse("bookings"))
            elif user.is_manager:
                return HttpResponseRedirect(reverse("company"))
            elif user.is_cleaner:
                return HttpResponseRedirect(reverse("cleaner"))
            elif user.is_client:
                return HttpResponseRedirect(reverse("client"))
            elif user.is_support_agent:
                return HttpResponseRedirect(reverse("support_tickets"))
        return dispatch

    def get_template_names(self):
        user = self.request.user
        if not user.is_authenticated:
            return self.public_homepage_name


class TermsOfUseView(generic.View):
    pass


class PrivacyPolicyView(generic.View):
    pass


class CustomSignUpView(SignupView):

    def get_initial(self):
        initial = super().get_initial()
        initial["email"] = self.request.GET.get("email")
        return initial


class CleanerSignUpView(SignupView):

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["role"] = self.kwargs.get("role")
        kwargs["invite_id"] = self.request.GET.get("invite_id")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class ProfileUpdateView(LoginRequiredMixin, SuccessMessageMixin, generic.UpdateView):
    template_name = "users/profile_update.html"
    form_class = ProfileForm
    success_message = "Done!"

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse("homepage")


class VerificationsView(LoginRequiredMixin, generic.ListView):
    template_name = "users/verifications.html"
    ordering = ["-id"]

    def get_queryset(self):
        user = self.request.user
        if user.is_cleaner:
            qs = user.userverificationdocument_set.filter(is_active=True)
        elif user.is_general_admin:
            qs = UserVerificationDocument.objects.filter(is_active=True)
        else:
            qs = UserVerificationDocument.objects.none()
        return qs

    def get(self, *args, **kwargs):
        user = self.request.user
        if user.is_cleaner:
            user.start_verification_process()
        return super().get(*args, **kwargs)


class UploadDocumentView(LoginRequiredMixin, CleanerAccessMixin, SuccessMessageMixin, generic.UpdateView):
    template_name = "users/upload_document.html"
    model = UserVerificationDocument
    form_class = UserVerificationDocumentForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.file and obj.status != obj.STATUS_REJECTED:
            messages.info(request, "This document has been already uploaded!")
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_success_url(self):
        return reverse("verification")


class VerificationDocumentActionView(LoginRequiredMixin, GeneralAdminAccessMixin, generic.DetailView):
    model = UserVerificationDocument
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get(self, *args, **kwargs):
        obj = self.get_object()
        action = kwargs.get("action")
        if action in ["approve", "reject"]:
            if action == "approve":
                obj.status = obj.STATUS_APPROVED
            elif action == "reject":
                obj.status = obj.STATUS_REJECTED
            obj.save(force_update=True)
            messages.success(self.request, "Done!")
        return HttpResponseRedirect(self.request.META.get("HTTP_REFERER", "/"))
