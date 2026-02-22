from django.urls import path
from .views import send_sms_view, campaign_upload_view, download_model_excel, dashboard_view, admin_dashboard_view

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('admin/dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('send/', send_sms_view, name='send_sms'),
    path('campaign/upload/', campaign_upload_view, name='campaign_upload'),
    path('campaign/model/', download_model_excel, name='download_model'),
]