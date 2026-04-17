from pathlib import Path

from django.conf import settings


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
