import os
import shutil
import subprocess
import sys
import threading
import importlib
from pathlib import Path

from django.conf import settings

from .models import FloorplanJob
from .services import build_expected_output_paths, get_source_stem


REPO_ROOT = Path(settings.BASE_DIR).parent

REQUIRED_PIPELINE_MODULES = [
    ('cv2', 'opencv-python'),
    ('numpy', 'numpy'),
    ('torch', 'torch'),
    ('segmentation_models_pytorch', 'segmentation-models-pytorch'),
]

PIPELINE_LOCK = threading.Lock()


def _run_command(args, *, env=None):
    merged_env = _pipeline_env(env)

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


def _pipeline_env(extra=None):
    merged_env = os.environ.copy()
    if extra:
        merged_env.update(extra)
    merged_env.setdefault('PYTHONIOENCODING', 'utf-8')
    merged_env.setdefault('PYTHONUTF8', '1')
    merged_env.setdefault('PYTHONHASHSEED', '0')
    merged_env.setdefault('OMP_NUM_THREADS', '1')
    merged_env.setdefault('OPENBLAS_NUM_THREADS', '1')
    merged_env.setdefault('MKL_NUM_THREADS', '1')
    merged_env.setdefault('VECLIB_MAXIMUM_THREADS', '1')
    merged_env.setdefault('NUMEXPR_NUM_THREADS', '1')
    return merged_env


def _copy_if_exists(src: Path, dst: Path):
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def _unlink_if_exists(path: Path):
    if path.exists() and path.is_file():
        path.unlink()


def _check_pipeline_dependencies():
    missing = []
    for module_name, package_name in REQUIRED_PIPELINE_MODULES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            missing.append(package_name)
    return missing


def _job_output_roots(job: FloorplanJob):
    source_stem = job.metadata.get('source_stem') or get_source_stem(job.original_filename, f'job_{job.id}')
    planned = build_expected_output_paths(job.id, source_stem)
    return source_stem, {key: Path(value) for key, value in planned.items()}


def _pipeline_outputs(source_stem: str):
    return {
        'door_mask_path': REPO_ROOT / 'predictions' / f'{source_stem}_door.png',
        'window_mask_path': REPO_ROOT / 'predictions' / f'{source_stem}_window.png',
        'geometry_path': REPO_ROOT / 'predictions' / f'{source_stem}_geometry.json',
        'overlay_path': REPO_ROOT / 'predictions' / f'overlay_{source_stem}.png',
        'combined_overlay_path': REPO_ROOT / 'predictions' / f'combined_overlay_{source_stem}.png',
        'wall_polygons_path': REPO_ROOT / 'intermediate' / 'wall_polygons.json',
        'room_polygons_path': REPO_ROOT / 'intermediate' / 'room_polygons.json',
        'fused_floorplan_path': REPO_ROOT / 'intermediate' / 'floorplan_fused.json',
    }


def seed_demo_job(job: FloorplanJob):
    source_stem, planned = _job_output_roots(job)
    sample_stem = '36'

    samples = _pipeline_outputs(sample_stem)

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
    outputs = _pipeline_outputs(source_stem)

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

    source_stem, _ = _job_output_roots(job)
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
        pipeline_outputs = _pipeline_outputs(source_stem)
        wall_stage_dir = REPO_ROOT / 'wall_pipeline' / 'data' / 'intermediate'
        placed_doors_path = REPO_ROOT / 'placed_doors.json'

        with PIPELINE_LOCK:
            for transient_path in [
                pipeline_outputs['door_mask_path'],
                pipeline_outputs['window_mask_path'],
                pipeline_outputs['geometry_path'],
                pipeline_outputs['overlay_path'],
                pipeline_outputs['combined_overlay_path'],
                pipeline_outputs['wall_polygons_path'],
                pipeline_outputs['room_polygons_path'],
                pipeline_outputs['fused_floorplan_path'],
                placed_doors_path,
                wall_stage_dir / 'wall_polygons.json',
                wall_stage_dir / 'room_polygons.json',
            ]:
                _unlink_if_exists(transient_path)

            command_log.append(_run_command([python, '-m', 'wall_pipeline.main', str(image_path)]))

            wall_src = wall_stage_dir / 'wall_polygons.json'
            room_src = wall_stage_dir / 'room_polygons.json'
            if wall_src.exists():
                shutil.copyfile(wall_src, pipeline_outputs['wall_polygons_path'])
            if room_src.exists():
                shutil.copyfile(room_src, pipeline_outputs['room_polygons_path'])

            command_log.append(_run_command([python, '-m', 'opening_pipeline.test_final', '--image', str(image_path)]))
            geometry_output = pipeline_outputs['geometry_path']
            command_log.append(
                _run_command(
                    [
                        python,
                        '-m',
                        'opening_pipeline.mask_to_geometry',
                        '--image',
                        str(image_path),
                        '--door_mask',
                        str(pipeline_outputs['door_mask_path']),
                        '--window_mask',
                        str(pipeline_outputs['window_mask_path']),
                        '--out_json',
                        str(geometry_output),
                        '--out_annotated',
                        str(REPO_ROOT / 'predictions' / f'{source_stem}_annotated.png'),
                    ]
                )
            )

            if not geometry_output.exists() or geometry_output.stat().st_size == 0:
                raise RuntimeError(
                    f'Geometry output was not generated for {source_stem}. '
                    'The mask-to-geometry step completed without writing the expected JSON file.'
                )

            env = _pipeline_env(
                {
                    'IMAGE_ID': source_stem,
                    'S2FP_GEOMETRY_PATH': str(geometry_output),
                    'S2FP_WALLS_PATH': str(pipeline_outputs['wall_polygons_path']),
                    'S2FP_ROOMS_PATH': str(pipeline_outputs['room_polygons_path']),
                    'S2FP_PLACED_DOORS_PATH': str(placed_doors_path),
                }
            )
            command_log.append(_run_command([python, '-m', 'opening_pipeline.run_transform'], env=env))
            command_log.append(
                _run_command(
                    [
                        python,
                        '-m',
                        'opening_pipeline.overlay',
                        str(image_path),
                        '--doors',
                        str(placed_doors_path),
                    ],
                    env=env,
                )
            )
            command_log.append(
                _run_command(
                    [
                        python,
                        '-m',
                        'utils.floorplan_fusion',
                        '--walls',
                        str(pipeline_outputs['wall_polygons_path']),
                        '--doors',
                        str(placed_doors_path),
                        '--geometry',
                        str(geometry_output),
                        '--out',
                        str(pipeline_outputs['fused_floorplan_path']),
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
                        str(pipeline_outputs['fused_floorplan_path']),
                        '--doors',
                        str(placed_doors_path),
                        '--out',
                        str(pipeline_outputs['combined_overlay_path']),
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
