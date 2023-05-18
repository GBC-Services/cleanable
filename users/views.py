from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404


class Homepage(generic.TemplateView):
    template_name = "users/homepage.html"


class TermsOfUseView(generic.View):
    pass


class PrivacyPolicyView(generic.View):
    pass