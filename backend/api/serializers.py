from rest_framework import serializers
from pathlib import Path
from django.conf import settings

from .models import FloorplanJob


class FloorplanJobSerializer(serializers.ModelSerializer):
    original_image_url = serializers.SerializerMethodField()
    door_mask_url = serializers.SerializerMethodField()
    window_mask_url = serializers.SerializerMethodField()
    overlay_url = serializers.SerializerMethodField()
    combined_overlay_url = serializers.SerializerMethodField()

    class Meta:
        model = FloorplanJob
        fields = [
            'id',
            'name',
            'description',
            'status',
            'original_filename',
            'original_image',
            'original_image_url',
            'annotations',
            'door_mask_path',
            'window_mask_path',
            'door_mask_url',
            'window_mask_url',
            'geometry_path',
            'overlay_path',
            'overlay_url',
            'combined_overlay_path',
            'combined_overlay_url',
            'wall_polygons_path',
            'room_polygons_path',
            'fused_floorplan_path',
            'metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'status',
            'door_mask_path',
            'window_mask_path',
            'geometry_path',
            'overlay_path',
            'combined_overlay_path',
            'wall_polygons_path',
            'room_polygons_path',
            'fused_floorplan_path',
            'created_at',
            'updated_at',
        ]

    def get_original_image_url(self, obj):
        request = self.context.get('request')
        if not obj.original_image:
            return None
        url = obj.original_image.url
        return request.build_absolute_uri(url) if request else url

    def _build_media_url(self, value):
        if not value:
            return None
        request = self.context.get('request')
        media_root = Path(settings.MEDIA_ROOT).resolve()
        target = Path(value).resolve()
        if not target.exists():
            return None
        try:
            relative = target.relative_to(media_root)
        except ValueError:
            return None
        url = f"{settings.MEDIA_URL}{relative.as_posix()}"
        return request.build_absolute_uri(url) if request else url

    def get_door_mask_url(self, obj):
        return self._build_media_url(obj.door_mask_path)

    def get_window_mask_url(self, obj):
        return self._build_media_url(obj.window_mask_path)

    def get_overlay_url(self, obj):
        return self._build_media_url(obj.overlay_path)

    def get_combined_overlay_url(self, obj):
        return self._build_media_url(obj.combined_overlay_path)
