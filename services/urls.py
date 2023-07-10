from django.urls import include, path
from . import views


urlpatterns = [
    path('services', views.ServicesView.as_view(), name='services'),
    path('service-checklist/<uuid>', views.ServicesChecklistView.as_view(), name='service_checklist'),

    path('service-fees-snapshot-creation/', views.ServiceFeesSnapshotCreationView.as_view(),
         name='service_fees_snapshot_creation'),

    path('send-fees-to-subcontractor/<uuid>', views.SendFeesToSubcontractorView.as_view(),
         name="send_fees_to_subcontractor"),

    path('create-subcontractors-fees/<uuid>', views.CreateSubcontractorsFeesView.as_view(), name='create_subcontractors_fees'),

]