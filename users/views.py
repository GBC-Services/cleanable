from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404


class Homepage(generic.TemplateView):
    client_template_name = "clients/homepage.html"
    manager_template_name = "companies/homepage.html"
    cleaner_template_name = "cleaners/homepage.html"
    default_template_name = "users/default_homepage.html"
    public_homepage_name = "users/public_homepage.html"

    def get_template_names(self):
        user = self.request.user
        if user.is_authenticated:
            if user.is_client:
                return self.client_template_name
            elif user.is_manager:
                return self.manager_template_name
            elif user.is_cleaner:
                return self.cleaner_template_name
            else:
                return self.default_template_name
        else:
            return self.public_homepage_name


class TermsOfUseView(generic.View):
    pass


class PrivacyPolicyView(generic.View):
    pass