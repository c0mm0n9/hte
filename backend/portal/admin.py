from django.contrib import admin
from .models import Device, DeviceWhitelist, DeviceBlacklist, VisitedSite


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('label', 'uuid', 'parent', 'device_type', 'created_at')
    list_filter = ('device_type', 'parent')
    search_fields = ('label', 'uuid')
    readonly_fields = ('uuid',)


@admin.register(DeviceWhitelist)
class DeviceWhitelistAdmin(admin.ModelAdmin):
    list_display = ('device', 'value', 'created_at')
    list_filter = ('device',)
    search_fields = ('value',)


@admin.register(DeviceBlacklist)
class DeviceBlacklistAdmin(admin.ModelAdmin):
    list_display = ('device', 'value', 'created_at')
    list_filter = ('device',)
    search_fields = ('value',)


@admin.register(VisitedSite)
class VisitedSiteAdmin(admin.ModelAdmin):
    list_display = ('url', 'device', 'visited_at', 'ai_detected', 'fake_news_detected', 'harmful_content_detected')
    list_filter = ('ai_detected', 'fake_news_detected', 'harmful_content_detected', 'device')
    search_fields = ('url', 'title')
    date_hierarchy = 'visited_at'
