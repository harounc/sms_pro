from django.urls import path
from .views import (
    send_sms_view, campaign_upload_view, download_model_excel, dashboard_view, 
    admin_dashboard_view, message_history_view, senders_list, sender_create, 
    sender_edit, sender_delete,
    admin_senders, approve_sender, reject_sender,
    message_search_api
)

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('admin/dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('send/', send_sms_view, name='send_sms'),
    path('campaign/upload/', campaign_upload_view, name='campaign_upload'),
    path('history/', message_history_view, name='message_history'),
    path('campaign/model/', download_model_excel, name='download_model'),

    # Entreprise Sender
    path('senders/', senders_list, name='senders_list'),
    path('senders/create/', sender_create, name='sender_create'),
    path('senders/<int:pk>/edit/', sender_edit, name='sender_edit'),
    path('senders/<int:pk>/delete/', sender_delete, name='sender_delete'),

    # Admin Sender Management
    path('admin/senders/', admin_senders, name='admin_senders'),
    path('admin/senders/<int:sender_id>/approve/', approve_sender, name='approve_sender'),
    path('admin/senders/<int:sender_id>/reject/', reject_sender, name='reject_sender'),


    # History
    path('api/messages/search', message_search_api, name='message_search'),
]