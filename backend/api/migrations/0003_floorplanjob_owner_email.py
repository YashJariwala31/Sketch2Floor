from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0002_floorplanjob_annotations"),
    ]

    operations = [
        migrations.AddField(
            model_name="floorplanjob",
            name="owner_email",
            field=models.EmailField(blank=True, db_index=True, default="", max_length=254),
        ),
    ]
