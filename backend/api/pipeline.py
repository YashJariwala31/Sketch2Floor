import json
import os
import shutil
import subprocess
import sys
import threading
import importlib
from pathlib import Path

from django.conf import settings

from .models import FloorplanJob
from .services import build_expected_output_paths


REPO_ROOT = Path(settings.BASE_DIR).parent

REQUIRED_PIPELINE_MODULES = [
    ('cv2', 'opencv-python'),
    ('numpy', 'numpy'),
    ('torch', 'torch'),
    ('segmentation_models_pytorch', 'segmentation-models-pytorch'),
]


def _run_command(args, *, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env.setdefault('PYTHONIOENCODING', 'utf-8')
    merged_env.setdefault('PYTHONUTF8', '1')

    completed = subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        env=merged_env,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        'args': args,
        'stdout': completed.stdout,
        'stderr': completed.stderr,
    }


def _copy_if_exists(src: Path, dst: Path):
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _check_pipeline_dependencies():
    missing = []
    for module_name, package_name in REQUIRED_PIPELINE_MODULES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(package_name)
    return missing


def _job_output_roots(job: FloorplanJob):
    source_stem = job.metadata.get('source_stem') or Path(job.original_filename or f'job_{job.id}').stem
    planned = build_expected_output_paths(job.id, source_stem)
    return source_stem, {key: Path(value) for key, value in planned.items()}


def seed_demo_job(job: FloorplanJob):
    source_stem, planned = _job_output_roots(job)
    sample_stem = '36'

    samples = {
        'door_mask_path': REPO_ROOT / 'predictions' / f'{sample_stem}_door.png',
        'window_mask_path': REPO_ROOT / 'predictions' / f'{sample_stem}_window.png',
        'geometry_path': REPO_ROOT / 'predictions' / f'{sample_stem}_geometry.json',
        'overlay_path': REPO_ROOT / 'predictions' / f'overlay_{sample_stem}.png',
        'combined_overlay_path': REPO_ROOT / 'predictions' / f'combined_overlay_{sample_stem}.png',
        'wall_polygons_path': REPO_ROOT / 'intermediate' / 'wall_polygons.json',
        'room_polygons_path': REPO_ROOT / 'intermediate' / 'room_polygons.json',
        'fused_floorplan_path': REPO_ROOT / 'intermediate' / 'floorplan_fused.json',
    }

    for field, sample_path in samples.items():
        _copy_if_exists(sample_path, planned[field])
        setattr(job, field, str(planned[field]))

    job.status = FloorplanJob.Status.COMPLETED
    job.metadata = {
        **job.metadata,
        'pipeline_state': 'demo_seeded',
        'source_stem': source_stem,
        'demo_source_stem': sample_stem,
    }
    job.save()


def _sync_pipeline_outputs(job: FloorplanJob):
    source_stem, planned = _job_output_roots(job)

    outputs = {
        'door_mask_path': REPO_ROOT / 'predictions' / f'{source_stem}_door.png',
        'window_mask_path': REPO_ROOT / 'predictions' / f'{source_stem}_window.png',
        'geometry_path': REPO_ROOT / 'predictions' / f'{source_stem}_geometry.json',
        'overlay_path': REPO_ROOT / 'predictions' / f'overlay_{source_stem}.png',
        'combined_overlay_path': REPO_ROOT / 'predictions' / f'combined_overlay_{source_stem}.png',
        'wall_polygons_path': REPO_ROOT / 'intermediate' / 'wall_polygons.json',
        'room_polygons_path': REPO_ROOT / 'intermediate' / 'room_polygons.json',
        'fused_floorplan_path': REPO_ROOT / 'intermediate' / 'floorplan_fused.json',
    }

    copied = {}
    for field, src in outputs.items():
        copied[field] = _copy_if_exists(src, planned[field])
        setattr(job, field, str(planned[field]))

    job.metadata = {
        **job.metadata,
        'pipeline_state': 'outputs_synced',
        'source_stem': source_stem,
        'copied_outputs': copied,
    }
    job.save()


def process_floorplan_job(job_id: int):
    job = FloorplanJob.objects.get(pk=job_id)
    if not job.original_image:
        job.status = FloorplanJob.Status.FAILED
        job.metadata = {**job.metadata, 'error': 'No original image uploaded.'}
        job.save(update_fields=['status', 'metadata', 'updated_at'])
        return

    source_stem, _planned = _job_output_roots(job)
    image_path = Path(job.original_image.path)
    python = sys.executable
    missing_dependencies = _check_pipeline_dependencies()

    try:
        if missing_dependencies:
            raise RuntimeError(
                "Missing backend pipeline dependencies: "
                + ", ".join(missing_dependencies)
                + ". Install them with `pip install -r backend/requirements-pipeline.txt` in the Python environment that runs Django."
            )

        job.status = FloorplanJob.Status.PROCESSING
        job.metadata = {
            **job.metadata,
            'pipeline_state': 'running',
            'source_stem': source_stem,
            'python_executable': python,
        }
        job.save(update_fields=['status', 'metadata', 'updated_at'])

        command_log = []
        command_log.append(_run_command([python, '-m', 'wall_pipeline.main', str(image_path)]))

        wall_src = REPO_ROOT / 'wall_pipeline' / 'data' / 'intermediate' / 'wall_polygons.json'
        room_src = REPO_ROOT / 'wall_pipeline' / 'data' / 'intermediate' / 'room_polygons.json'
        if wall_src.exists():
            shutil.copyfile(wall_src, REPO_ROOT / 'intermediate' / 'wall_polygons.json')
        if room_src.exists():
            shutil.copyfile(room_src, REPO_ROOT / 'intermediate' / 'room_polygons.json')

        command_log.append(_run_command([python, '-m', 'opening_pipeline.test_final', '--image', str(image_path)]))
        command_log.append(
            _run_command(
                [
                    python,
                    '-m',
                    'opening_pipeline.mask_to_geometry',
                    '--image',
                    str(image_path),
                    '--door_mask',
                    str(REPO_ROOT / 'predictions' / f'{source_stem}_door.png'),
                    '--window_mask',
                    str(REPO_ROOT / 'predictions' / f'{source_stem}_window.png'),
                    '--out_json',
                    str(REPO_ROOT / 'predictions' / f'{source_stem}_geometry.json'),
                    '--out_annotated',
                    str(REPO_ROOT / 'predictions' / f'{source_stem}_annotated.png'),
                ]
            )
        )

        env = os.environ.copy()
        env['IMAGE_ID'] = source_stem
        command_log.append(_run_command([python, '-m', 'opening_pipeline.run_transform'], env=env))
        command_log.append(_run_command([python, '-m', 'opening_pipeline.overlay', str(image_path)]))
        command_log.append(
            _run_command(
                [
                    python,
                    '-m',
                    'utils.floorplan_fusion',
                    '--walls',
                    str(REPO_ROOT / 'intermediate' / 'wall_polygons.json'),
                    '--doors',
                    str(REPO_ROOT / 'placed_doors.json'),
                    '--out',
                    str(REPO_ROOT / 'intermediate' / 'floorplan_fused.json'),
                ]
            )
        )
        command_log.append(
            _run_command(
                [
                    python,
                    '-m',
                    'utils.combined_overlay',
                    '--image',
                    str(image_path),
                    '--walls',
                    str(REPO_ROOT / 'intermediate' / 'wall_polygons.json'),
                    '--doors',
                    str(REPO_ROOT / 'placed_doors.json'),
                    '--out',
                    str(REPO_ROOT / 'predictions' / f'combined_overlay_{source_stem}.png'),
                ]
            )
        )

        _sync_pipeline_outputs(job)
        job.status = FloorplanJob.Status.COMPLETED
        job.metadata = {
            **job.metadata,
            'pipeline_state': 'completed',
            'command_log': command_log,
        }
        job.save(update_fields=['status', 'metadata', 'updated_at'])
    except subprocess.CalledProcessError as exc:
        job.status = FloorplanJob.Status.FAILED
        job.metadata = {
            **job.metadata,
            'pipeline_state': 'failed',
            'error': str(exc),
            'stdout': exc.stdout,
            'stderr': exc.stderr,
            'python_executable': python,
        }
        job.save(update_fields=['status', 'metadata', 'updated_at'])
    except Exception as exc:
        job.status = FloorplanJob.Status.FAILED
        job.metadata = {
            **job.metadata,
            'pipeline_state': 'failed',
            'error': str(exc),
        }
        job.save(update_fields=['status', 'metadata', 'updated_at'])


def start_floorplan_job_async(job_id: int):
    thread = threading.Thread(target=process_floorplan_job, args=(job_id,), daemon=True)
    thread.start()
    return thread
