from django.db.models import Q
from .models import CleaningType, RegularityType, Cleaning, AssignedCleaner
from companies.models import Company
from django.http import HttpResponseRedirect
from django.urls import reverse


class CleaningAccessMixin:

    def get_queryset(self):
        qs = Cleaning.objects.none()  # return None by default
        user = self.request.user
        if user.is_client:
            cleanings_ids = user.get_ordered_cleanings(as_cleaning_ids=True)
            return super().get_queryset().filter(id__in=cleanings_ids)
        else:
            company_uuid = self.request.session["company_uuid"]
            if not company_uuid:
                return HttpResponseRedirect(reverse("company_select"))
            if user.is_cleaner:
                company = Company.objects.get(uuid=company_uuid)
                if company.get_is_user_cleaner(user):
                    cleanings_ids = company.get_assigned_user_cleanings(user, as_cleaning_ids=True)
                    return super().get_queryset().filter(id__in=cleanings_ids)
            elif user.is_manager:
                company = Company.objects.get(uuid=company_uuid)
                if company.get_is_user_manager(user):
                    cleaning_ids = company.get_cleanings(as_cleaning_ids=True)
                    return super().get_queryset().filter(id__in=cleaning_ids)
        return qs


class ClientPlacesForFormMixin:

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["place"].queryset = user.get_places()


class CleaningMixin(ClientPlacesForFormMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cleaning_type"].queryset = CleaningType.objects.filter(company__isnull=True, is_active=True)
        self.fields["regularity_type"].queryset = RegularityType.objects.filter(company__isnull=True, is_active=True)
