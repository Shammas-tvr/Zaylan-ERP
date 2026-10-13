from django.db import migrations


def backfill(apps, schema_editor):
    Organization = apps.get_model("tenancy", "Organization")
    Branch = apps.get_model("branches", "Branch")
    InventoryLocation = apps.get_model("inventory", "InventoryLocation")
    for organization in Organization.objects.all():
        InventoryLocation.objects.get_or_create(
            organization=organization,
            kind="CENTRAL_KITCHEN",
            defaults={"name": "Central kitchen"},
        )
        InventoryLocation.objects.get_or_create(
            organization=organization,
            kind="IN_TRANSIT",
            defaults={"name": "In transit"},
        )
    for branch in Branch.objects.all():
        InventoryLocation.objects.get_or_create(
            organization_id=branch.organization_id,
            branch=branch,
            defaults={"kind": "BRANCH", "name": branch.name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_stock_ledger"),
        ("branches", "0003_stock_ledger"),
        ("tenancy", "0002_brand_admin_username_portal"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
