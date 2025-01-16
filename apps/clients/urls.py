from django.urls import include, path
from . import views


urlpatterns = [
    path('main', views.ClientView.as_view(), name='client'),
    path('client/<uuid>', views.ClientView.as_view(), name='any_client'),

    path('places', views.PlacesView.as_view(), name='places'),
    path('place/<uuid>', views.PlaceView.as_view(), name='place'),
    path('place-create', views.PlaceCreateUpdateView.as_view(), name='place_create'),
    path('place/update/<uuid>', views.PlaceCreateUpdateView.as_view(), name='place_update'),

    path('region-zone-not-covered', views.RegionZoneNotCoveredView.as_view(), name='region_zone_not_covered'),
    path('log-mapbox-request', views.LogMapboxRequestView.as_view(), name='log_mapbox_request'),
]
