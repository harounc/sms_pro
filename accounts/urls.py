from django.urls import path
from .views import login_view
from . import views


urlpatterns = [

    # Login
    path("login/", login_view, name="login"),

    # Accounts Dashboard
    path("dashboard/", views.accounts_dashboard_view, name="accounts_dashboard"),
    
    # Company Management
    path("companies/", views.company_list_view, name="company_list"),
    path("companies/<int:company_id>/users/", views.company_users_list_view, name="company_users_list"),
    path("companies/<int:company_id>/users/create/", views.company_user_create_view, name="company_user_create"),
    path("companies/<int:company_id>/users/<int:user_id>/edit/", views.company_user_update_view, name="company_user_update"),
    path("companies/<int:company_id>/users/<int:user_id>/toggle-active/", views.company_user_toggle_active_view, name="company_user_toggle_active"),
    path("companies/<int:company_id>/users/<int:user_id>/recharge/", views.company_user_recharge_view, name="company_user_recharge"),
    path("companies/<int:company_id>/users/<int:user_id>/delete/", views.company_user_delete_view, name="company_user_delete"),
    
    # Company CRUD
    path("companies/create/", views.company_create_view, name="company_create"),
    path("companies/<int:pk>/edit/", views.company_update_view, name="company_update"),
    path("companies/<int:pk>/delete/", views.company_delete_view, name="company_delete"),
    path("companies/<int:pk>/recharge/", views.company_recharge_view, name="company_recharge"),


    # User Profile
    path("profile/", views.user_profile_view, name="user_profile"),


    # Toggle Company Active
    path("companies/<int:pk>/toggle/", views.company_toggle_active_view, name="company_toggle_active"),

]