from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from .models import Company, CompanyDocument, CompanyServiceFeesSnapshot
from .forms import CompanyForm, CompanyDocumentForm
from apps.cleanings.forms import CleanerAssignForm
from apps.utils.mixins.access_mixins import (GeneralAdminAccessMixin, ManagerAccessMixin, GeneralAdminOrManagerAccessMixin)
from apps.utils.mixins.queryset_mixins import CompaniesMixin


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


# class CompanyCreateView(LoginRequiredMixin, GeneralAdminAccessMixin, CompaniesMixin,
#                         generic.CreateView):
#     template_name = "companies/company_create_update.html"
#     model = Company
#     form_class = CompanyCreateForm
#     success_message = "Done!"
#     success_url = reverse_lazy("companies")


class CompanyUpdateView(LoginRequiredMixin, GeneralAdminOrManagerAccessMixin, CompaniesMixin,
                        SuccessMessageMixin, generic.UpdateView):
    template_name = "companies/company_create_update.html"
    model = Company
    form_class = CompanyForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def get_object(self, queryset=None):
        try:
            self.object = super().get_object(queryset)
            return self.object
        except AttributeError:
            return None

    def get_success_url(self):
        if self.request.user.is_general_admin:
            return reverse("companies")
        else:
            return reverse("company")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class CompanyDocumentCreateUpdateView(LoginRequiredMixin, GeneralAdminAccessMixin, generic.UpdateView):
    template_name = "companies/company_document_create_update.html"
    model = CompanyDocument
    form_class = CompanyDocumentForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def get_success_url(self):
        return reverse("companies")

    def get_object(self, queryset=None):
        try:
            self.object = super().get_object(queryset)
            return self.object
        except AttributeError:
            return None

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.company = self.get_company()
        obj.save()
        messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())

    def get_company(self):
        try:
            company = Company.objects.get(uuid=self.kwargs.get("company_uuid"))
        except Company.DoesNotExist:
            company = None
        return company


class CompanyContactsView(LoginRequiredMixin, GeneralAdminAccessMixin, CompaniesMixin, generic.DetailView):
    template_name = "companies/company_contacts.html"
    model = Company
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


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
        return HttpResponseRedirect(reverse("company"))


class CompanyCleanersView(LoginRequiredMixin, ManagerAccessMixin, CompaniesMixin,
                          generic.DetailView):
    template_name = "companies/company_cleaners.html"
    model = Company
    slug_field = "uuid"
    slug_url_kwarg = "uuid"