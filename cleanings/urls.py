from django.urls import include, path
from . import views


urlpatterns = [
    path('cleanings', views.CleaningsView.as_view(), name='cleanings'),
    path('cleanings/<uuid>', views.CleaningsView.as_view(), name='any_cleaner_cleanings'),

    path('cleaning/update/<uuid>', views.CleaningCreateUpdateView.as_view(), name='cleaning_update'),
    path('cleaning/<uuid>', views.CleaningView.as_view(), name='cleaning'),
    path('assign-cleaner-for-cleaning', views.AssignCleanerForCleaningView.as_view(), name='assign_cleaner_for_cleaning'),

    path('withdraw-cleaning/<uuid>', views.WithdrawCleaningView.as_view(), name='withdraw_cleaning'),
    path('set-next-status-for-cleaning/<uuid>', views.SetNextStatusForCleaningView.as_view(),
         name='set_next_status_for_cleaning'),

    path('cleaner-comment/<uuid>', views.CleanerCommentView.as_view(),
         name='cleaner_comment'),
    path('report-issue-for-cleaning/<uuid>', views.ReportIssueForCleaningView.as_view(),
         name='report_issue_for_cleaning'),

    path('cleaning-save-current-location/<uuid>', views.CleaningSaveCurrentLocationView.as_view(),
         name='cleaning_save_current_location'),

    path('send-chat-message-ajax/<uuid>', views.SendMessageAjaxView.as_view(), name='send_chat_message_ajax'),
]