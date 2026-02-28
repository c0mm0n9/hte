from django.urls import path
from . import views

urlpatterns = [
    path('', views.api_health),  # ALB health check: GET /api/portal/
    path('validate/', views.api_validate_key),
    path('blacklist/', views.api_blacklist),
    path('csrf/', views.api_csrf),
    path('login/', views.api_login),
    path('logout/', views.api_logout),
    path('me/', views.api_me),
    path('register/', views.api_register),
    path('devices/', views.api_devices_list),
    path('devices/<int:device_id>/', views.api_device_delete),
    path('devices/<int:device_id>/whitelist/<int:entry_id>/', views.api_device_whitelist_delete),
    path('devices/<int:device_id>/whitelist/', views.api_device_whitelist_add),
    path('devices/<int:device_id>/blacklist/<int:entry_id>/', views.api_device_blacklist_delete),
    path('devices/<int:device_id>/blacklist/', views.api_device_blacklist_add),
    path('visited-sites/', views.api_visited_sites_list),
    path('visited-sites/<int:device_id>/', views.api_visited_sites_list),
    path('record-visit/', views.api_record_visit),
    path('dashboard/', views.api_dashboard),
]
