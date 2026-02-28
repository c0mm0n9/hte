# Generated manually: backfill existing devices with suggested whitelist/blacklist

from django.db import migrations


SUGGESTED_WHITELIST = [
    'youtube.com',
    'kids.youtube.com',
    'pbskids.org',
    'nickjr.com',
    'disneyjunior.com',
    'khanacademy.org',
    'duolingo.com',
    'nationalgeographic.com',
    'abcya.com',
]
SUGGESTED_BLACKLIST = [
    'pornhub.com',
    'xvideos.com',
    'xnxx.com',
    'redtube.com',
    'youporn.com',
    'xhamster.com',
]


def backfill_suggested(apps, schema_editor):
    Device = apps.get_model('portal', 'Device')
    DeviceWhitelist = apps.get_model('portal', 'DeviceWhitelist')
    DeviceBlacklist = apps.get_model('portal', 'DeviceBlacklist')
    for device in Device.objects.all():
        for value in SUGGESTED_WHITELIST:
            DeviceWhitelist.objects.get_or_create(device=device, value=value)
        for value in SUGGESTED_BLACKLIST:
            DeviceBlacklist.objects.get_or_create(device=device, value=value)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0003_add_whitelist_blacklist'),
    ]

    operations = [
        migrations.RunPython(backfill_suggested, noop),
    ]
