from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from allauth.account.views import SignupView


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