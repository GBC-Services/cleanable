from django.urls import reverse, reverse_lazy
from django.views import generic
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import SupportTicket, SupportTicketMessage
from apps.companies.models import CompanyServiceFeesSnapshot, CompanyServiceFee
from .forms import SupportTicketForm, SupportTicketMessageForm
from apps.utils.mixins.access_mixins import GeneralAdminAccessMixin, GeneralAdminOrManagerOrCleanerAccessMixin
from apps.locations.models import Region
from django.db import transaction
from django.contrib.messages.views import SuccessMessageMixin
from apps.utils.mixins.queryset_mixins import SupportTicketMixin
from apps.utils.mixins.access_mixins import SupportAgentAccessMixin, GeneralAdminOrClientOrSupportAgentAccessMixin


class SupportTicketsView(LoginRequiredMixin, GeneralAdminOrClientOrSupportAgentAccessMixin, SupportTicketMixin,
                         generic.ListView):
    template_name = "support/support_tickets.html"
    model = SupportTicket


class SupportTicketView(LoginRequiredMixin, generic.DetailView,  SuccessMessageMixin,
                        GeneralAdminOrClientOrSupportAgentAccessMixin, SupportTicketMixin,
                        generic.FormView):
    template_name = "support/support_ticket.html"
    model = SupportTicket
    slug_field = "uuid"
    slug_url_kwarg = "uuid"
    form_class = SupportTicketMessageForm
    success_message = "Done!"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            self.object = self.get_object()
            if request.user.is_support_agent and not self.get_object().assigned_to:
                self.object.assigned_to = user
                self.object.save(force_update=True)
                messages.success(request, "Done!")
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def form_valid(self, form):
        data = form.cleaned_data
        user = self.request.user
        support_ticket = self.get_object()
        text = data["text"]
        kwargs = dict(user=user, text=text, support_ticket=support_ticket)
        if user.is_general_admin or user.is_support_agent:
            status = data["status"]
            support_ticket.status = status
            support_ticket.save(force_update=True)
        if text:
            SupportTicketMessage.objects.create(**kwargs)
        return super().form_valid(form)

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["user"] = self.request.user
        return form_kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial["status"] = self.get_object().status
        return initial


class SupportTicketCreateView(LoginRequiredMixin, generic.CreateView):
    template_name = "support/support_ticket_create.html"
    model = SupportTicket
    form_class = SupportTicketForm
    success_url = reverse_lazy("support_tickets")

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["user"] = self.request.user
        return form_kwargs
