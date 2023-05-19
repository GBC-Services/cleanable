from django.urls import include, path
from . import views


urlpatterns = [
    path('cleaning-request/<uuid>', views.CleaningRequestCreateUpdateView.as_view(),
         name='cleaning_request_update'),
    path('cleaning-request-create', views.CleaningRequestCreateUpdateView.as_view(),
         name='cleaning_request_create'),
    path('cleanings', views.CleaningsView.as_view(), name='cleanings'),
    path('cleaning/update/<uuid>', views.CleaningCreateUpdateView.as_view(), name='cleaning_update'),
    path('cleaning/<uuid>', views.CleaningView.as_view(), name='cleaning'),
]