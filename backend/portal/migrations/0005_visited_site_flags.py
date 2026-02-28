# Add three flags (has_harmful_content, has_pii, has_predators) and updated_at to VisitedSite

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0004_backfill_suggested_lists'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitedsite',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='visitedsite',
            name='has_harmful_content',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='visitedsite',
            name='has_pii',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='visitedsite',
            name='has_predators',
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name='visitedsite',
            constraint=models.UniqueConstraint(fields=('device', 'url'), name='portal_visitedsite_device_url_unique'),
        ),
    ]
