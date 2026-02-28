# Replace Child with Device: create Device, migrate VisitedSite to device FK, remove Child

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_children_to_devices(apps, schema_editor):
    Child = apps.get_model('portal', 'Child')
    Device = apps.get_model('portal', 'Device')
    VisitedSite = apps.get_model('portal', 'VisitedSite')
    child_to_device = {}
    for child in Child.objects.all():
        device = Device.objects.create(
            parent_id=child.parent_id,
            label=child.name,
            uuid=uuid.uuid4(),
            device_type='control',
            agentic_prompt='',
        )
        child_to_device[child.id] = device
    for site in VisitedSite.objects.all():
        site.device_id = child_to_device[site.child_id].id
        site.save(update_fields=['device_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=255)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('device_type', models.CharField(choices=[('control', 'Control'), ('agentic', 'Agentic')], default='control', max_length=20)),
                ('agentic_prompt', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['label'],
            },
        ),
        migrations.AddField(
            model_name='visitedsite',
            name='device',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='visited_sites', to='portal.device'),
        ),
        migrations.RunPython(migrate_children_to_devices, noop),
        migrations.RemoveField(
            model_name='visitedsite',
            name='child',
        ),
        migrations.AlterField(
            model_name='visitedsite',
            name='device',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visited_sites', to='portal.device'),
        ),
        migrations.DeleteModel(
            name='Child',
        ),
    ]
