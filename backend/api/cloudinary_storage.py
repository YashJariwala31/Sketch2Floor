from pathlib import Path
import re

import cloudinary
import cloudinary.uploader
from django.conf import settings


IMAGE_URL_FIELDS = {
    'original_image': 'original_image_cloud_url',
    'door_mask_path': 'door_mask_cloud_url',
    'window_mask_path': 'window_mask_cloud_url',
    'overlay_path': 'overlay_cloud_url',
    'combined_overlay_path': 'combined_overlay_cloud_url',
}


def cloudinary_enabled() -> bool:
    return bool(getattr(settings, 'CLOUDINARY_URL', ''))


def safe_public_id_part(value: str, fallback: str = 'shared') -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_-]+', '_', value or '').strip('_')
    return cleaned or fallback


def upload_file(path, *, public_id: str, resource_type: str = 'auto') -> str:
    target = Path(path)
    if not target.exists() or not target.is_file():
        return ''

    result = cloudinary.uploader.upload(
        str(target),
        public_id=public_id,
        resource_type=resource_type,
        overwrite=True,
    )
    return result.get('secure_url') or result.get('url') or ''


def upload_job_artifacts(job) -> dict:
    if not cloudinary_enabled():
        return {}

    owner = safe_public_id_part(job.owner_email)
    base_public_id = f"sketch2floorplan/{owner}/jobs/{job.id}"
    uploaded = {}

    original_path = getattr(getattr(job, 'original_image', None), 'path', '')
    if original_path:
        uploaded['original_image'] = upload_file(original_path, public_id=f"{base_public_id}/original")

    path_fields = [
        'door_mask_path',
        'window_mask_path',
        'overlay_path',
        'combined_overlay_path',
    ]
    for field in path_fields:
        local_path = getattr(job, field, '')
        stem = Path(local_path).stem if local_path else field
        uploaded[field] = upload_file(local_path, public_id=f"{base_public_id}/{stem}")

    update_fields = []
    for source_field, cloud_field in IMAGE_URL_FIELDS.items():
        url = uploaded.get(source_field)
        if url:
            setattr(job, cloud_field, url)
            update_fields.append(cloud_field)

    if update_fields:
        job.save(update_fields=[*update_fields, 'updated_at'])

    return {key: value for key, value in uploaded.items() if value}
