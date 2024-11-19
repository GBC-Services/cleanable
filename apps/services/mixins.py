from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import SubcontractorsFeesForm
from apps.utils.mixins.access_mixins import GeneralAdminAccessMixin


class SubcontractorsFeesMixin(LoginRequiredMixin, GeneralAdminAccessMixin, generic.DetailView, generic.FormView):
    form_class = SubcontractorsFeesForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["snapshot"] = self.get_object()
        return kwargs