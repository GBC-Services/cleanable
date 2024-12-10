from django.views import generic
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from .models import Cleaning, SpecialCleaningRequest
from .forms import (ClientCleaningForm, CleanerCleaningForm, ManagerCleaningForm, SupportAgentCleaningForm,
                    CleaningsFilterForm, CleaningIssueForm,
                    CleaningCommentOnlyForm,
                    MessageForm, SpecialRequestForm)
from apps.utils.mixins.access_mixins import (GeneralAdminAccessMixin, CleanerAccessMixin, ManagerAccessMixin,
                                             GeneralAdminOrManagerOrCleanerAccessMixin, ManagerOrCleanerAccessMixin,
                                             CleaningAccessMixin, CleanerOrSupportAccessMixin, ClientAccessMixin)
from apps.utils.mixins.queryset_mixins import CleaningsMixin, CleaningUpdateMixin, SpecialCleaningRequestsMixin
from django.http import JsonResponse
import datetime
from django.urls import reverse
from django.http import HttpResponse


class CleaningsView(LoginRequiredMixin,
                    GeneralAdminOrManagerOrCleanerAccessMixin, CleaningsMixin,
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


class CleaningView(LoginRequiredMixin, CleaningAccessMixin, CleaningsMixin,
                   generic.DetailView, generic.FormView):
    template_name = "cleanings/cleaning.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = MessageForm


class CleaningCreateUpdateView(LoginRequiredMixin, SuccessMessageMixin, CleanerOrSupportAccessMixin,
                               CleaningUpdateMixin, generic.UpdateView):
    template_name = "cleanings/cleaning_create_update.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def get_form_class(self):
        user = self.request.user
        obj = self.get_object()
        if obj.status == obj.STATUS_COMPLETED:
            return CleaningCommentOnlyForm
        else:
            if user.is_client:
                return ClientCleaningForm
            elif obj:
                if user.is_cleaner:
                    return CleanerCleaningForm
                elif user.is_manager:
                    return ManagerCleaningForm
                elif user.is_support_agent:
                    return SupportAgentCleaningForm
            return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_success_url(self):
        return self.get_object().get_absolute_url()


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


class SpecialRequestsView(LoginRequiredMixin, ManagerAccessMixin, SpecialCleaningRequestsMixin, generic.ListView):
    template_name = "cleanings/special_requests.html"
    model = SpecialCleaningRequest


class SpecialRequestRespondView(LoginRequiredMixin, ManagerAccessMixin, SpecialCleaningRequestsMixin,
                                SuccessMessageMixin, generic.UpdateView):
    template_name = "cleanings/special_request_respond.html"
    model = SpecialCleaningRequest
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = SpecialRequestForm
    success_message = "Done!"

    def get_success_url(self):
        return reverse("company")

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.status = SpecialCleaningRequest.STATUS_ACCEPTED
        obj.save()
        return HttpResponseRedirect(self.get_success_url())


class SpecialRequestRejectView(LoginRequiredMixin, ManagerAccessMixin, SpecialCleaningRequestsMixin,
                               generic.DetailView):
    model = SpecialCleaningRequest
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get(self, *args, **kwargs):
        self.get_object().set_status(SpecialCleaningRequest.STATUS_CANCELLED_BY_COMPANY)
        messages.success(self.request, "Done!")
        return HttpResponseRedirect(reverse("company"))


class CalendarDataView(LoginRequiredMixin, ClientAccessMixin, generic.DetailView):
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(booking__client=self.request.user)

    def get(self, *args, **kwargs):
        obj = self.get_object()
        response = HttpResponse(obj.get_data_for_calendar())
        response['Content-Disposition'] = f"attachment; filename={obj.get_title()}.ics"
        return response
