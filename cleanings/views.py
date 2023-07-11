from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from .models import Cleaning
from .forms import (ClientCleaningForm, CleanerCleaningForm, ManagerCleaningForm,
                    CleaningsFilterForm, CleaningIssueForm, MessageForm)
from utils.mixins.access_mixins import (GeneralAdminAccessMixin, CleanerAccessMixin, ManagerAccessMixin,
                                        GeneralAdminOrManagerOrCleanerAccessMixin, ManagerOrCleanerAccessMixin)
from utils.mixins.queryset_mixins import CleaningsMixin
from django.http import JsonResponse
import datetime


class CleaningsView(LoginRequiredMixin, GeneralAdminOrManagerOrCleanerAccessMixin, CleaningsMixin,
                    generic.ListView, generic.FormView):
    template_name = "cleanings/cleanings.html"
    model = Cleaning
    form_class = CleaningsFilterForm

    def get_queryset(self):
        qs = super().get_queryset().order_by("-scheduled_date", "-scheduled_start_dt")
        if self.request.GET.get("date"):
            date = datetime.datetime.strptime(self.request.GET.get("date"), "%m/%d/%Y")
            qs = qs.filter(scheduled_date=date)
        return qs

    def get_initial(self):
        initial = super().get_initial()
        initial["date"] = self.request.GET.get("date")
        return initial


class CleaningView(LoginRequiredMixin, GeneralAdminOrManagerOrCleanerAccessMixin, CleaningsMixin,
                   generic.DetailView, generic.FormView):
    template_name = "cleanings/cleaning.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = MessageForm


class CleaningCreateUpdateView(LoginRequiredMixin, SuccessMessageMixin, CleanerAccessMixin, generic.UpdateView):
    template_name = "cleanings/cleaning_create_update.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def get_queryset(self):
        return self.request.user.get_cleanings()

    def get_form_class(self):
        user = self.request.user
        if user.is_client:
            return ClientCleaningForm
        elif self.get_object():
            if user.is_cleaner:
                return CleanerCleaningForm
            elif user.is_manager:
                return ManagerCleaningForm
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs


class AssignCleanerForCleaningView(LoginRequiredMixin, ManagerAccessMixin, generic.View):

    def post(self, *args, **kwargs):
        data = self.request.POST
        user = self.request.user
        company = user.company
        cleaning_uuid = data.get("cleaning_uuid")
        cleaner_uuid = data.get("cleaner_uuid")
        cleaning = Cleaning.objects.get(uuid=cleaning_uuid, company=company)
        cleaner = company.get_cleaners().filter(uuid=cleaner_uuid).last()
        cleaning.assign_cleaner(cleaner)
        return JsonResponse(dict(status="success"))


class WithdrawCleaningView(LoginRequiredMixin, GeneralAdminAccessMixin, CleaningsMixin, generic.DetailView):
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get(self, *args, **kwargs):
        self.get_object().set_status(Cleaning.STATUS_CANCELLED_BY_SERVICE)
        messages.success(self.request, "Done!")
        return HttpResponseRedirect(self.request.META.get("HTTP_REFERER", "/"))


class SetNextStatusForCleaningView(LoginRequiredMixin, ManagerOrCleanerAccessMixin, CleaningsMixin,
                                   generic.DetailView):
        model = Cleaning
        slug_field = "uuid"
        slug_url_kwarg = "uuid"

        def get(self, *args, **kwargs):
            self.get_object().set_next_status()
            messages.success(self.request, "Done!")
            return HttpResponseRedirect(self.request.META.get("HTTP_REFERER", "/"))


class CleanerCommentView(LoginRequiredMixin, SuccessMessageMixin, CleanerAccessMixin, CleaningsMixin,
                         generic.UpdateView):
    template_name = "cleanings/cleaning_issue_reporting.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = CleaningIssueForm
    success_message = "Done!"

    def get_success_url(self):
        return self.get_object().get_absolute_url()


class ReportIssueForCleaningView(CleanerCommentView):

    def form_valid(self, form):
        self.get_object().set_status(Cleaning.STATUS_NOT_COMPLETED)
        return super().form_valid(form)


class CleaningSaveCurrentLocationView(LoginRequiredMixin, SuccessMessageMixin, CleanerAccessMixin,  generic.DetailView):
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def post(self, *args, **kwargs):
        data = self.request.POST
        self.get_object().save_coordinates(f"{data.get('lat')}, {data.get('lng')}")
        return JsonResponse(dict(status="success"))


class SendMessageAjaxView(LoginRequiredMixin, ManagerOrCleanerAccessMixin, CleaningsMixin, generic.DetailView, generic.FormView):
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = MessageForm

    def form_valid(self, form):
        message = form.cleaned_data.get("message")
        message = self.get_object().save_chat_message(self.request.user, message)
        message_html = render_to_string(template_name="cleanings/partials/message.html",
                                        context=dict(request=self.request, message=message))
        return JsonResponse(dict(status="success", message_html=message_html))

    def form_invalid(self, form):
        return JsonResponse(dict(status="error"))