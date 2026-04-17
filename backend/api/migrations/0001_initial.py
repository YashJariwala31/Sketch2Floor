from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='FloorplanJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=120)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('queued', 'Queued'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='draft', max_length=24)),
                ('original_image', models.ImageField(blank=True, null=True, upload_to='uploads/originals/')),
                ('original_filename', models.CharField(blank=True, max_length=255)),
                ('door_mask_path', models.CharField(blank=True, max_length=255)),
                ('window_mask_path', models.CharField(blank=True, max_length=255)),
                ('geometry_path', models.CharField(blank=True, max_length=255)),
                ('overlay_path', models.CharField(blank=True, max_length=255)),
                ('combined_overlay_path', models.CharField(blank=True, max_length=255)),
                ('wall_polygons_path', models.CharField(blank=True, max_length=255)),
                ('room_polygons_path', models.CharField(blank=True, max_length=255)),
                ('fused_floorplan_path', models.CharField(blank=True, max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
