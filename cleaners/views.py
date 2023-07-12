from django.urls import reverse, reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from .models import CompanyCleanerInvite, SchedulePeriod, ScheduleTimeSlot, CleanerSchedule
from users.models import User
from .forms import CompanyCleanerInviteForm, CleanerScheduleForm
from utils.mixins.access_mixins import (GeneralAdminOrManagerOrCleanerAccessMixin,
                                        ManagerOrCleanerAccessMixin, ManagerAccessMixin, CleanerAccessMixin)
from utils.mixins.queryset_mixins import CleanerMixin, ScheduleMixin
from django.contrib import messages
from django.db import transaction


class CleanerView(LoginRequiredMixin, ManagerOrCleanerAccessMixin, CleanerMixin, generic.DetailView):
    template_name = "cleaners/cleaner.html"
    model = User
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class CleanerInviteCreateView(LoginRequiredMixin, ManagerAccessMixin, generic.CreateView):
    template_name = "cleaners/cleaner_invite_create.html"
    model = CompanyCleanerInvite
    form_class = CompanyCleanerInviteForm

    def form_valid(self, form):
        object = form.save(commit=False)
        object.company = self.request.user.company
        object.save()
        return HttpResponseRedirect(reverse_lazy("cleaners"))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs


class CleanerDeleteView(LoginRequiredMixin, ManagerAccessMixin, generic.DetailView):
    model = CompanyCleanerInvite
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def get(self, *args, **kwargs):
        object = self.get_object()
        object.is_active = False
        if object.user:
            object.user.is_active = False
        object.save()

        messages.success(self.request, "Done!")
        return HttpResponseRedirect(reverse("cleaners"))


class CleanerScheduleView(LoginRequiredMixin, ManagerOrCleanerAccessMixin, ScheduleMixin, generic.DetailView):
    template_name = "cleaners/cleaner_schedule.html"
    model = User
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    next_week = False


class ManageCleanerScheduleView(LoginRequiredMixin, CleanerAccessMixin, ScheduleMixin, generic.DetailView):
    template_name = "cleaners/manage_cleaner_schedule.html"
    model = User
    extra_context = dict(is_update=True)
    next_week = True

    def get_object(self, queryset=None):
        return self.request.user

    def post(self, *args, **kwargs):
        user = self.request.user
        error_message = None
        with transaction.atomic():
            period = None
            cleaner_schedule_ids = list()
            for k, v in self.request.POST.items():
                if k.startswith("cleaner_schedule_uuid"):
                    uuid = k.split("cleaner_schedule_uuid_")[-1]
                    form = CleanerScheduleForm(dict(is_active=v))
                    if form.is_valid():
                        is_active = form.cleaned_data.get("is_active")
                        try:
                            cleaner_schedule = CleanerSchedule.objects.get(uuid=uuid, user=user)
                            cleaner_schedule.is_active = is_active
                            cleaner_schedule.save(force_update=True)

                            cleaner_schedule_ids.append(cleaner_schedule.id)
                            period = cleaner_schedule.period
                        except CleanerSchedule.DoesNotExist:
                            error_message = "Error!"
                            break
                    else:
                        error_message = str(form.errors)
                        break
            if not period is None:
                CleanerSchedule.objects.filter(user=user, period=period).exclude(id__in=cleaner_schedule_ids)\
                    .update(is_active=False)

        if error_message:
            messages.error(self.request, error_message)
        else:
            messages.success(self.request, "Done!")
        url = f"{reverse('cleaner_own_schedule')}?{self.request.GET.urlencode()}"
        return HttpResponseRedirect(url)
