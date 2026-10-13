from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_item_tracks_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="expiry_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
