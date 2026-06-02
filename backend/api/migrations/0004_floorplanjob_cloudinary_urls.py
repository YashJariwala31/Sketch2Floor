from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0003_floorplanjob_owner_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="floorplanjob",
            name="combined_overlay_cloud_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="floorplanjob",
            name="door_mask_cloud_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="floorplanjob",
            name="original_image_cloud_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="floorplanjob",
            name="overlay_cloud_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="floorplanjob",
            name="window_mask_cloud_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
