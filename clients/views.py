from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Place
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from .forms import PlaceForm


class PlacesView(LoginRequiredMixin, generic.ListView):
    template_name = "clients/places.html"
    model = Place

    def get_queryset(self):
        qs = super().get_queryset().filter(user=self.request.user)
        return qs


class PlaceCreateUpdateView(LoginRequiredMixin, SuccessMessageMixin, generic.UpdateView):
    template_name = "clients/place_create_update.html"
    model = Place
    form_class = PlaceForm
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
        return reverse("places")

    def form_valid(self, form):
        object = form.save(commit=False)
        if not self.get_object():
            object.user = self.request.user
        object.save()
        return HttpResponseRedirect(self.get_success_url())


class PlaceView(LoginRequiredMixin, generic.DetailView):
    template_name = "clients/place.html"
    model = Place
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
