"""
URL configuration for cleaning project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from . settings import DEBUG, MEDIA_ROOT, MEDIA_URL, STATIC_ROOT, STATIC_URL
from django.views import defaults as default_views
from allauth.account.views import LoginView
from axes.decorators import axes_dispatch
from axes.decorators import axes_form_invalid
from django.utils.decorators import method_decorator
LoginView.dispatch = method_decorator(axes_dispatch)(LoginView.dispatch)
LoginView.form_invalid = method_decorator(axes_form_invalid)(LoginView.form_invalid)
from django.contrib.admin.views.decorators import staff_member_required

# Ensure users go through the allauth workflow when logging into admin.
admin.site.login = staff_member_required(admin.site.login, login_url='/accounts/login')
# Run the standard admin set-up.
admin.autodiscover()

urlpatterns = [
  path('adminishidden/', admin.site.urls),
  path('', include('bookings.urls')),
  path('', include('cleaners.urls')),
  path('', include('cleanings.urls')),
  path('', include('clients.urls')),
  path('', include('companies.urls')),
  path('', include('services.urls')),
  path('', include('subscriptions.urls')),
  path('', include('users.urls')),
  path('accounts/', include('allauth.urls')),
] \
  + static(STATIC_URL, document_root=STATIC_ROOT) \
  + static(MEDIA_URL, document_root=MEDIA_ROOT)
