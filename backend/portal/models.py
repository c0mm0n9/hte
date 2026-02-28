import uuid
from django.db import models
from django.contrib.auth.models import User


class Device(models.Model):
    """A device linked to a parent. Control = parent-defined prompt; Agentic = predetermined settings."""
    TYPE_CONTROL = 'control'
    TYPE_AGENTIC = 'agentic'
    TYPE_CHOICES = [
        (TYPE_CONTROL, 'Control'),
        (TYPE_AGENTIC, 'Agentic'),
    ]

    label = models.CharField(max_length=255)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_CONTROL)
    # For control: parent-defined prompt. Blank for agentic (predetermined).
    agentic_prompt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return f"{self.label} ({self.get_device_type_display()})"


class DeviceWhitelist(models.Model):
    """Allowed site/domain for a device (e.g. youtube.com, kids.youtube.com)."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='whitelist_entries')
    value = models.CharField(max_length=500)  # domain or URL pattern
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['value']
        unique_together = [('device', 'value')]

    def __str__(self):
        return f"{self.device.label}: {self.value}"


class DeviceBlacklist(models.Model):
    """Blocked site/domain for a device (e.g. 18+ sites)."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='blacklist_entries')
    value = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['value']
        unique_together = [('device', 'value')]

    def __str__(self):
        return f"{self.device.label}: {self.value}"


class VisitedSite(models.Model):
    """A website visit recorded by the extension (visited list / history)."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='visited_sites')
    url = models.URLField(max_length=2048)
    title = models.CharField(max_length=512, blank=True)
    visited_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Three flags for AI detection (future); extension sends false until AI runs
    has_harmful_content = models.BooleanField(default=False)
    has_pii = models.BooleanField(default=False)
    has_predators = models.BooleanField(default=False)

    # Legacy detection fields (kept for backward compat; can sync from flags)
    ai_detected = models.BooleanField(default=False)
    fake_news_detected = models.BooleanField(default=False)
    harmful_content_detected = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-visited_at']
        constraints = [
            models.UniqueConstraint(fields=['device', 'url'], name='portal_visitedsite_device_url_unique'),
        ]

    def __str__(self):
        return f"{self.url} ({self.visited_at.date()})"
