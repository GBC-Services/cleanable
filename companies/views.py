from django.urls import reverse, reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from .models import Company, CompanyServiceFeesSnapshot, CompanyServiceFee
from .forms import CompanyCreateForm, CompanyForm
from cleanings.forms import CleanerAssignForm
from utils.mixins.access_mixins import (GeneralAdminAccessMixin, ManagerAccessMixin, GeneralAdminOrManagerAccessMixin)
from utils.mixins.queryset_mixins import CompaniesMixin


class CompaniesView(LoginRequiredMixin, GeneralAdminAccessMixin, generic.ListView):
    template_name = "companies/companies.html"
    model = Company
    ordering = "-id"


class CompanyView(LoginRequiredMixin, GeneralAdminOrManagerAccessMixin, CompaniesMixin,
                  generic.DetailView):
    template_name = "companies/company.html"
    model = Company
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_anonymous:
            self.cleanings = self.get_object().get_cleanings_to_assign()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        context_data = super().get_form_kwargs()
        context_data["company"] = self.get_object()
        return context_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cleanings"] = self.cleanings
        context["forms_by_dates"] = self.get_forms_by_dates()
        return context

    def get_forms_by_dates(self):
        forms_by_dates = dict()
        dates = list(set(self.cleanings.values_list("booking__scheduled_date", flat=True)))
        for date in dates:
            forms_by_dates[date] = CleanerAssignForm(company=self.object, date=date)
        return forms_by_dates


class CompanyCreateView(LoginRequiredMixin, GeneralAdminAccessMixin, CompaniesMixin,
                        generic.CreateView):
    template_name = "companies/company_create_update.html"
    model = Company
    form_class = CompanyCreateForm
    success_message = "Done!"
    success_url = reverse_lazy("companies")


class CompanyUpdateView(LoginRequiredMixin, ManagerAccessMixin, CompaniesMixin, generic.UpdateView):
    template_name = "companies/company_create_update.html"
    model = Company
    form_class = CompanyForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"
    success_url = reverse_lazy("my_company")


class CompanyServiceFeesView(LoginRequiredMixin, GeneralAdminOrManagerAccessMixin, CompaniesMixin,
                             generic.DetailView):
    template_name = "companies/company_service_fees.html"
    model = Company
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AcceptCompanyFeesView(LoginRequiredMixin, ManagerAccessMixin, generic.DetailView):
    model = CompanyServiceFeesSnapshot
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def get(self, *args, **kwargs):
        is_accepted = self.get_object().accept()
        if is_accepted:
            messages.success(self.request, "Done!")
        else:
            messages.error(self.request, "Error! It has been already accepted before!")
        return HttpResponseRedirect(reverse("my_company"))