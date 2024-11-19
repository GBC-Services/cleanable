from django.urls import include, path
from . import views


urlpatterns = [
    path('support-tickets', views.SupportTicketsView.as_view(), name='support_tickets'),
    path('support-ticket/<uuid>/', views.SupportTicketView.as_view(), name='support_ticket'),
    path('support-ticket-create', views.SupportTicketCreateView.as_view(), name='support_ticket_create'),
]