from django.db import models


class FloorplanJob(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        QUEUED = 'queued', 'Queued'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    owner_email = models.EmailField(max_length=254, blank=True, default='', db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    original_image = models.ImageField(upload_to='uploads/originals/', blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True)

    door_mask_path = models.CharField(max_length=255, blank=True)
    window_mask_path = models.CharField(max_length=255, blank=True)
    geometry_path = models.CharField(max_length=255, blank=True)
    overlay_path = models.CharField(max_length=255, blank=True)
    combined_overlay_path = models.CharField(max_length=255, blank=True)
    wall_polygons_path = models.CharField(max_length=255, blank=True)
    room_polygons_path = models.CharField(max_length=255, blank=True)
    fused_floorplan_path = models.CharField(max_length=255, blank=True)

    original_image_cloud_url = models.URLField(max_length=500, blank=True)
    door_mask_cloud_url = models.URLField(max_length=500, blank=True)
    window_mask_cloud_url = models.URLField(max_length=500, blank=True)
    overlay_cloud_url = models.URLField(max_length=500, blank=True)
    combined_overlay_cloud_url = models.URLField(max_length=500, blank=True)

    # Client-authored interactive annotations (e.g., measurement dimensions).
    # Stored in image-render coordinates (relative to the rendered/fit image),
    # so the frontend can keep them anchored while zooming/panning.
    annotations = models.JSONField(default=list, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name or f'FloorplanJob #{self.pk}'
