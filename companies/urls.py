from django.urls import include, path
from . import views


urlpatterns = [
    path('companies', views.CompaniesView.as_view(), name='companies'),
    path('company', views.CompanyView.as_view(), name='company'),
    path('company/<uuid>', views.CompanyView.as_view(), name='any_company'),
    path('company-create', views.CompanyCreateView.as_view(), name='company_create'),
    path('company/update/<uuid>', views.CompanyUpdateView.as_view(), name='company_update'),

    path('company-service-fees/<uuid>', views.CompanyServiceFeesView.as_view(), name='any_company_service_fees'),
    path('company-service-fees', views.CompanyServiceFeesView.as_view(), name='company_service_fees'),

    path('accept-company-fees/<uuid>', views.AcceptCompanyFeesView.as_view(), name='accept_company_fees'),

    path('company-cleaners', views.CompanyCleanersView.as_view(), name='company_cleaners'),
    path('company-cleaners/<uuid>', views.CompanyCleanersView.as_view(), name='any_company_cleaners'),
]