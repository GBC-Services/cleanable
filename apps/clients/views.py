from django.urls import reverse
from django.views import generic
from django.http import HttpResponseRedirect, Http404
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Place
from django.conf import settings
from django.contrib.messages.views import SuccessMessageMixin
from .forms import PlaceForm
from apps.utils.mixins.access_mixins import GeneralAdminOrClientAccessMixin, ClientAccessMixin
from apps.utils.mixins.queryset_mixins import PlacesMixin, ClientMixin
from apps.users.models import User
from django.utils.translation import gettext as _


class ClientView(LoginRequiredMixin, GeneralAdminOrClientAccessMixin, ClientMixin,
                 generic.DetailView):
    template_name = "clients/client.html"
    model = User
    slug_field = "uuid"
    slug_url_kwarg = "uuid"

    def get_object(self, queryset=None):
        user = self.request.user
        if user.is_client:
            return user
        elif self.kwargs.get(self.slug_url_kwarg):
            return super().get_object(queryset)
        else:
            raise Http404(
                _("No %(verbose_name)s found matching the query")
                % {"verbose_name": self.model._meta.verbose_name}
            )


class PlacesView(LoginRequiredMixin, GeneralAdminOrClientAccessMixin, PlacesMixin,
                 generic.ListView):
    template_name = "clients/places.html"
    model = Place


class PlaceView(LoginRequiredMixin, GeneralAdminOrClientAccessMixin, PlacesMixin,
                generic.DetailView):
    template_name = "clients/place.html"
    model = Place
    slug_field = "uuid"
    slug_url_kwarg = "uuid"


class PlaceCreateUpdateView(LoginRequiredMixin, SuccessMessageMixin, ClientAccessMixin, PlacesMixin,
                            generic.UpdateView):
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

    def get_initial(self):
        initial = super().get_initial()
        if self.object:
            initial["state"] = self.object.state.name
            initial["city"] = self.object.city.name
            initial["zip_code"] = self.object.zip_code.value
        return initial

    def form_valid(self, form):
        object = form.save(commit=False)
        if not self.get_object():
            object.client = self.request.user
        object.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        return context