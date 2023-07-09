from django.urls import include, path
from . import views


urlpatterns = [
    path('cleaners', views.CleanersView.as_view(), name='cleaners'),
    path('my-dashboard', views.CleanerView.as_view(), name='cleaner'),
    path('cleaner/<uuid>', views.CleanerView.as_view(), name='any_cleaner'),
    path('cleaner-invite/create', views.CleanerInviteCreateView.as_view(), name='cleaner_invite_create'),
    path('cleaner-delete/<uuid>', views.CleanerDeleteView.as_view(), name='cleaner_delete'),

    path('cleaner-schedule', views.CleanerScheduleView.as_view(), name='cleaner_own_schedule'),
    path('cleaner-schedule/<uuid>', views.CleanerScheduleView.as_view(), name='cleaner_schedule'),
    path('manage-cleaner-schedule', views.ManageCleanerScheduleView.as_view(), name='manage_cleaner_schedule'),
]