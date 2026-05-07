import shutil
from pathlib import Path

from django.conf import settings

from .models import FloorplanJob

OUTPUT_PATH_FIELDS = (
    'door_mask_path',
    'window_mask_path',
    'geometry_path',
    'overlay_path',
    'combined_overlay_path',
    'wall_polygons_path',
    'room_polygons_path',
    'fused_floorplan_path',
)


def build_expected_output_paths(job_id: int, source_stem: str) -> dict:
    media_root = Path(settings.MEDIA_ROOT)
    output_root = media_root / 'jobs' / str(job_id)
    predictions_root = output_root / 'predictions'
    intermediate_root = output_root / 'intermediate'

    return {
        'job_root': str(output_root),
        'predictions_root': str(predictions_root),
        'intermediate_root': str(intermediate_root),
        'door_mask_path': str(predictions_root / f'{source_stem}_door.png'),
        'window_mask_path': str(predictions_root / f'{source_stem}_window.png'),
        'geometry_path': str(predictions_root / f'{source_stem}_geometry.json'),
        'overlay_path': str(predictions_root / f'overlay_{source_stem}.png'),
        'combined_overlay_path': str(predictions_root / f'combined_overlay_{source_stem}.png'),
        'wall_polygons_path': str(intermediate_root / 'wall_polygons.json'),
        'room_polygons_path': str(intermediate_root / 'room_polygons.json'),
        'fused_floorplan_path': str(intermediate_root / 'floorplan_fused.json'),
    }


def get_source_stem(filename: str, fallback: str = 'floorplan') -> str:
    stem = Path(filename or fallback).stem
    return stem or fallback


def get_job_source_stem(job: FloorplanJob, fallback: str | None = None) -> str:
    fallback = fallback or f'job_{job.id}'
    image_field = getattr(job, 'original_image', None)

    if image_field:
        stored_name = getattr(image_field, 'name', '')
        if stored_name:
            stem = get_source_stem(stored_name, fallback)
            if stem:
                return stem

        try:
            stored_path = getattr(image_field, 'path', '')
        except (NotImplementedError, ValueError):
            stored_path = ''

        if stored_path:
            stem = get_source_stem(stored_path, fallback)
            if stem:
                return stem

    original_filename = getattr(job, 'original_filename', '')
    if original_filename:
        return get_source_stem(original_filename, fallback)

    metadata_stem = (getattr(job, 'metadata', {}) or {}).get('source_stem')
    if metadata_stem:
        return get_source_stem(metadata_stem, fallback)

    return fallback


def scaffold_job_outputs(job: FloorplanJob, source_stem: str) -> FloorplanJob:
    paths = build_expected_output_paths(job.id, source_stem)

    for field in OUTPUT_PATH_FIELDS:
        setattr(job, field, paths[field])

    job.metadata = {
        **job.metadata,
        'pipeline_state': 'scaffolded',
        'source_stem': source_stem,
    }
    job.save(update_fields=[*OUTPUT_PATH_FIELDS, 'metadata', 'updated_at'])
    return job


def mark_job_queued(job: FloorplanJob, pipeline_state: str) -> FloorplanJob:
    job.status = FloorplanJob.Status.QUEUED
    job.metadata = {
        **job.metadata,
        'pipeline_state': pipeline_state,
    }
    job.save(update_fields=['status', 'metadata', 'updated_at'])
    return job


def delete_job_assets(job: FloorplanJob) -> None:
    if job.original_image:
        job.original_image.delete(save=False)

    job_root = Path(settings.MEDIA_ROOT) / 'jobs' / str(job.id)
    if job_root.exists():
        shutil.rmtree(job_root, ignore_errors=True)
