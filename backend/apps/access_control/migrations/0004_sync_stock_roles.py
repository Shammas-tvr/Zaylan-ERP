from django.db import migrations


def sync_roles(apps, schema_editor):
    from apps.access_control.services import sync_system_roles
    from apps.tenancy.models import Organization

    for organization in Organization.objects.all():
        sync_system_roles(organization)


class Migration(migrations.Migration):
    dependencies = [
        ("access_control", "0003_tenant_consistency"),
    ]

    operations = [migrations.RunPython(sync_roles, migrations.RunPython.noop)]
