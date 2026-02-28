import uuid
from django.db import models
from django.contrib.auth.models import User


class Device(models.Model):
    """A device (browser/device) linked to a parent, with type: control (predetermined settings) or agentic (parent-defined AI prompt)."""
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
    # For agentic: parent-defined prompt for the agentic AI. Blank for control.
    agentic_prompt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return f"{self.label} ({self.get_device_type_display()})"


class VisitedSite(models.Model):
    """A website visit recorded by the extension, with detection results."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='visited_sites')
    url = models.URLField(max_length=2048)
    title = models.CharField(max_length=512, blank=True)
    visited_at = models.DateTimeField(auto_now_add=True)

    # Detection results (from extension / Docker services)
    ai_detected = models.BooleanField(default=False)
    fake_news_detected = models.BooleanField(default=False)
    harmful_content_detected = models.BooleanField(default=False)

    # Optional details (e.g. confidence, type of AI content)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-visited_at']

    def __str__(self):
        return f"{self.url} ({self.visited_at.date()})"
