from rest_framework import serializers
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError

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
            'original_image_cloud_url',
            'annotations',
            'door_mask_path',
            'window_mask_path',
            'door_mask_url',
            'window_mask_url',
            'door_mask_cloud_url',
            'window_mask_cloud_url',
            'geometry_path',
            'overlay_path',
            'overlay_url',
            'overlay_cloud_url',
            'combined_overlay_path',
            'combined_overlay_url',
            'combined_overlay_cloud_url',
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
            'original_image_cloud_url',
            'door_mask_cloud_url',
            'window_mask_cloud_url',
            'overlay_cloud_url',
            'combined_overlay_cloud_url',
            'created_at',
            'updated_at',
        ]

    def validate_original_image(self, value):
        if value:
            # 1. Size check: 10MB limit
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("Image file too large (max 10MB).")

            # 2. Extension check
            valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
            ext = Path(value.name).suffix.lower()
            if ext not in valid_extensions:
                raise serializers.ValidationError(
                    f"Unsupported file extension {ext}. Supported: {', '.join(valid_extensions)}"
                )

            # 3. Dimension check: Ensure it's a reasonably sized image
            from django.core.files.images import get_image_dimensions
            w, h = get_image_dimensions(value)
            if not w or not h:
                raise serializers.ValidationError("Could not determine image dimensions. The file may be corrupt.")
            if w < 300 or h < 300:
                raise serializers.ValidationError(
                    f"Image dimensions too small ({w}x{h}). Minimum 300x300 required for processing."
                )
            if w > 8000 or h > 8000:
                # Extremely large images might crash the server or ML pipeline
                raise serializers.ValidationError(
                    f"Image dimensions too large ({w}x{h}). Maximum 8000x8000 allowed."
                )

        return value

    def get_original_image_url(self, obj):
        if obj.original_image_cloud_url:
            return obj.original_image_cloud_url

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
        if obj.door_mask_cloud_url:
            return obj.door_mask_cloud_url
        return self._build_media_url(obj.door_mask_path)

    def get_window_mask_url(self, obj):
        if obj.window_mask_cloud_url:
            return obj.window_mask_cloud_url
        return self._build_media_url(obj.window_mask_path)

    def get_overlay_url(self, obj):
        if obj.overlay_cloud_url:
            return obj.overlay_cloud_url
        return self._build_media_url(obj.overlay_path)

    def get_combined_overlay_url(self, obj):
        if obj.combined_overlay_cloud_url:
            return obj.combined_overlay_cloud_url
        return self._build_media_url(obj.combined_overlay_path)


class FloorplanJobDetailSerializer(FloorplanJobSerializer):
    class Meta(FloorplanJobSerializer.Meta):
        read_only_fields = FloorplanJobSerializer.Meta.read_only_fields + [
            'metadata',
            'original_image',
            'original_filename',
        ]
