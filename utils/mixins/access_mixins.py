from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404
from django.urls import reverse


class GeneralAdminAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_general_admin:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class ManagerAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_manager:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class CleanerAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_cleaner:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class ManagerOrCleanerAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_manager and not user.is_cleaner:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class GeneralAdminOrManagerAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_manager and not user.is_superuser:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class ClientAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_client:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class ClientOrNotAuthAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not user.is_client:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class GeneralAdminOrClientAccessMixin:

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_general_admin and not request.user.is_client:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)