from django.urls import include, path
from . import views


urlpatterns = [
    path('places', views.PlacesView.as_view(), name='places'),
    path('place-create', views.PlaceCreateUpdateView.as_view(), name='place_create'),
    path('place/update/<uuid>', views.PlaceCreateUpdateView.as_view(), name='place_update'),
    path('place/<uuid>', views.PlaceView.as_view(), name='place'),
]