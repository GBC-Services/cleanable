from django.urls import reverse, reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from .models import Service, ServiceFeesSnapshot, ServiceFee
from companies.models import CompanyServiceFeesSnapshot, CompanyServiceFee
from .forms import RegionFilterForm, FeeForm, SubcontractorsFeesForm
from utils.mixins.access_mixins import GeneralAdminAccessMixin, GeneralAdminOrManagerOrCleanerAccessMixin
from locations.models import Region
from django.db import transaction
import time
from .mixins import SubcontractorsFeesMixin


class ServicesView(LoginRequiredMixin, GeneralAdminAccessMixin, generic.FormView, generic.ListView):
    template_name = "services/services.html"
    model = Service
    form_class = RegionFilterForm

    def dispatch(self, request, *args, **kwargs):
        data = self.request.GET
        region_slug = data.get("region")
        snapshot_uuid = data.get("snapshot")
        self.region = Region.objects.get(slug=region_slug) if region_slug else None
        if snapshot_uuid and self.region:
            self.snapshot = ServiceFeesSnapshot.objects.get(uuid=snapshot_uuid)
        elif self.region:
            self.snapshot = self.region.get_fees_last_snapshot()
        else:
            self.snapshot = None
        dispatch = super().dispatch(request, *args, **kwargs)
        return dispatch

    def get_queryset(self):
        if self.region:
            return super().get_queryset().filter(is_active=True).order_by("id")
        else:
            return self.model.objects.none()

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.request.GET)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["region"] = self.region
        context["snapshot"] = self.snapshot
        context["services"] = self.object_list
        return context


class ServicesChecklistView(LoginRequiredMixin, GeneralAdminOrManagerOrCleanerAccessMixin, generic.DetailView):
    template_name = "services/service_checklist.html"
    model = Service
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class ServiceFeesSnapshotCreationView(LoginRequiredMixin, GeneralAdminAccessMixin, generic.View):
    available_fee_types = ["client_fee", "subcontractor_fee"]

    def post(self, *args, **kwargs):
        exclude_fields = ["csrfmiddlewaretoken", "region"]
        region_uuid = self.request.POST.get("region")
        with transaction.atomic():
            region = Region.objects.get(uuid=region_uuid)
            snapshot = ServiceFeesSnapshot.objects.create(region=region)
            service_fees_dict = dict()
            for k, v in self.request.POST.items():
                if not k in exclude_fields:
                    fee_type, service_uuid = k.split("||")
                    service = Service.objects.get(uuid=service_uuid)
                    form = FeeForm(dict(fee=v))
                    val = v if form.is_valid() else 0
                    if fee_type in self.available_fee_types:
                        if not service_uuid in service_fees_dict:
                            kwargs = dict(snapshot=snapshot, service=service)
                            kwargs[fee_type] = val
                            service_fees_dict[service_uuid] = ServiceFee(**kwargs)
                        else:
                            setattr(service_fees_dict[service_uuid], fee_type, val)
            # service_fees = ServiceFee.objects.bulk_create(service_fees_dict.values())
            """To trigger a save method"""
            for service_fee in service_fees_dict.values():
                service_fee.save()

        messages.success(self.request, "Updated!")
        return HttpResponseRedirect(snapshot.get_url())


class SendFeesToSubcontractorView(SubcontractorsFeesMixin):
    template_name = "services/send_fees_to_subcontractor.html"
    model = ServiceFeesSnapshot
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class CreateSubcontractorsFeesView(SubcontractorsFeesMixin):
    model = ServiceFeesSnapshot
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_success_url(self):
        return reverse("services")

    def form_valid(self, form):
        exclude_fields = ["csrfmiddlewaretoken", "companies", "profit_rate"]
        companies = form.cleaned_data.get("companies")
        service_fees_snapshot = self.get_object()
        with transaction.atomic():
            for company in companies:
                """Deactivate current unapproved company's service fees snapshots"""
                CompanyServiceFeesSnapshot.objects.filter(company=company, is_accepted=False, is_active=True).update(is_active=False)

                snapshot = CompanyServiceFeesSnapshot.objects.create(company=company, service_fees_snapshot=service_fees_snapshot)
                for k, v in self.request.POST.items():
                    if not k in exclude_fields:
                        fee_type, service_uuid = k.split("||")
                        service = Service.objects.get(uuid=service_uuid)
                        form = FeeForm(dict(fee=v))
                        val = v if form.is_valid() else 0
                        if fee_type == "subcontractor_fee":
                            CompanyServiceFee.objects.create(snapshot=snapshot, company=company, service=service, fee=val)

        messages.success(self.request, "Done!")
        return HttpResponseRedirect(service_fees_snapshot.get_url())