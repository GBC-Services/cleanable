from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from .models import Cleaning, CleaningRequest
from .forms import CleaningRequestForm, ClientCleaningForm, CleanerCleaningForm, ManagerCleaningForm
from .mixins import CleaningAccessMixin


class CleaningRequestCreateUpdateView(LoginRequiredMixin, generic.UpdateView):
    template_name = "cleanings/cleaning_request_create_update.html"
    model = CleaningRequest
    form_class = CleaningRequestForm
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

    def dispatch(self, request, *args, **kwargs):
        dispatch = super().dispatch(request, *args, **kwargs)
        if not request.user.is_client:
            return HttpResponseForbidden()
        return dispatch

    def get_queryset(self):
        qs = super().get_queryset().filter(client=self.request.user)
        return qs

    def get_object(self, queryset=None):
        try:
            self.object = super().get_object(queryset)
            return self.object
        except AttributeError:
            return None

    def form_valid(self, form):
        user = self.request.user
        object = form.save(commit=False)
        object.client = user
        object.save()
        return HttpResponseRedirect(reverse("cleaning_request_update", kwargs=dict(uuid=object.uuid)))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        object = self.get_object()
        if object:
            initial["date"] = object.scheduled_start_dt.date()
            initial["time_from"] = object.scheduled_start_dt.time()
            initial["time_to"] = object.scheduled_end_dt.time()
        return initial


class CleaningsView(LoginRequiredMixin, generic.ListView, CleaningAccessMixin):
    template_name = "cleanings/cleanings.html"
    model = Cleaning


class CleaningCreateUpdateView(LoginRequiredMixin, SuccessMessageMixin, generic.UpdateView, CleaningAccessMixin):
    template_name = "cleanings/cleaning_create_update.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    success_message = "Done!"

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
        kwargs["user"] = self.request.user
        return kwargs


class CleaningView(LoginRequiredMixin, generic.DetailView, CleaningAccessMixin):
    template_name = "cleanings/cleaning.html"
    model = Cleaning
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
