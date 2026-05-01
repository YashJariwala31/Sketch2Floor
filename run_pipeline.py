"""Run the end-to-end pipeline for one image in a deterministic way."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
ORIGINAL_DIR = ROOT_DIR / "original"
PREDICTIONS_DIR = ROOT_DIR / "predictions"
INTERMEDIATE_DIR = ROOT_DIR / "intermediate"
WALL_STAGE_DIR = ROOT_DIR / "wall_pipeline" / "data" / "intermediate"


def _resolve_image_path(raw_value: str) -> tuple[Path, str]:
    input_path = Path(raw_value.strip('"').strip("'"))
    if input_path.exists() and input_path.is_file():
        return input_path, input_path.stem

    image_id = input_path.stem
    candidates = [
        ORIGINAL_DIR / f"{image_id}.jpeg",
        ORIGINAL_DIR / f"{image_id}.jpg",
        ORIGINAL_DIR / f"{image_id}.png",
    ]
    image_path = next((path for path in candidates if path.exists() and path.is_file()), None)
    if image_path is None:
        raise FileNotFoundError(f"Could not resolve an input image for '{raw_value}'.")
    return image_path, image_id


def _safe_unlink(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _cleanup_transient_outputs(paths: list[Path]) -> None:
    for path in paths:
        _safe_unlink(path)


def _deterministic_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONHASHSEED", "0")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("NUMEXPR_NUM_THREADS", "1")
    if extra:
        env.update(extra)
    return env


def _run(args: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(args, check=True, env=env)


image_input = input("Enter image number: ").strip()
image_path, image_id = _resolve_image_path(image_input)

print(f"[INFO] Using image_id={image_id} image_path={image_path}")

PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)

door_mask = PREDICTIONS_DIR / f"{image_id}_door.png"
window_mask = PREDICTIONS_DIR / f"{image_id}_window.png"
geometry_json = PREDICTIONS_DIR / f"{image_id}_geometry.json"
annotated_img = PREDICTIONS_DIR / f"{image_id}_annotated.png"
overlay_img = PREDICTIONS_DIR / f"overlay_{image_id}.png"
combined_overlay = PREDICTIONS_DIR / f"combined_overlay_{image_id}.png"

wall_dst = INTERMEDIATE_DIR / f"{image_id}_wall_polygons.json"
room_dst = INTERMEDIATE_DIR / f"{image_id}_room_polygons.json"
placed_doors = INTERMEDIATE_DIR / f"{image_id}_placed_doors.json"
fused_out = INTERMEDIATE_DIR / f"{image_id}_floorplan_fused.json"

legacy_wall_dst = INTERMEDIATE_DIR / "wall_polygons.json"
legacy_room_dst = INTERMEDIATE_DIR / "room_polygons.json"
legacy_fused_out = INTERMEDIATE_DIR / "floorplan_fused.json"
legacy_placed_doors = ROOT_DIR / "placed_doors.json"

_cleanup_transient_outputs(
    [
        door_mask,
        window_mask,
        geometry_json,
        annotated_img,
        overlay_img,
        combined_overlay,
        wall_dst,
        room_dst,
        placed_doors,
        fused_out,
        legacy_wall_dst,
        legacy_room_dst,
        legacy_fused_out,
        legacy_placed_doors,
        WALL_STAGE_DIR / "wall_polygons.json",
        WALL_STAGE_DIR / "room_polygons.json",
    ]
)

env = _deterministic_env(
    {
        "IMAGE_ID": image_id,
        "S2FP_GEOMETRY_PATH": str(geometry_json),
        "S2FP_WALLS_PATH": str(wall_dst),
        "S2FP_ROOMS_PATH": str(room_dst),
        "S2FP_PLACED_DOORS_PATH": str(placed_doors),
    }
)

print("[STEP 1] Running wall pipeline...")
_run([PYTHON, "-m", "wall_pipeline.main", str(image_path)], env=env)

wall_src = WALL_STAGE_DIR / "wall_polygons.json"
room_src = WALL_STAGE_DIR / "room_polygons.json"
if not wall_src.exists():
    raise FileNotFoundError(f"Wall polygons not generated: {wall_src}")

shutil.copyfile(wall_src, wall_dst)
shutil.copyfile(wall_src, legacy_wall_dst)

if room_src.exists():
    shutil.copyfile(room_src, room_dst)
    shutil.copyfile(room_src, legacy_room_dst)
else:
    print("[WARN] Room polygons not found, door orientation may be less accurate")

print("[STEP 2] Running detection...")
_run([PYTHON, "-m", "opening_pipeline.test_final", "--image", str(image_path)], env=env)

print("[STEP 3] Mask -> geometry...")
_run(
    [
        PYTHON,
        "-m",
        "opening_pipeline.mask_to_geometry",
        "--image",
        str(image_path),
        "--door_mask",
        str(door_mask),
        "--window_mask",
        str(window_mask),
        "--out_json",
        str(geometry_json),
        "--out_annotated",
        str(annotated_img),
    ],
    env=env,
)

if not geometry_json.exists() or geometry_json.stat().st_size == 0:
    raise SystemExit("[ERROR] Geometry output was not generated; aborting downstream steps.")

print("[STEP 4] Door placement...")
_run([PYTHON, "-m", "opening_pipeline.run_transform"], env=env)
if not placed_doors.exists() or placed_doors.stat().st_size == 0:
    raise SystemExit("[ERROR] Door placement output was not generated.")
shutil.copyfile(placed_doors, legacy_placed_doors)

print("[STEP 5] Overlay...")
_run(
    [
        PYTHON,
        "-m",
        "opening_pipeline.overlay",
        str(image_path),
        "--doors",
        str(placed_doors),
    ],
    env=env,
)

print("[STEP 6] Fuse walls + doors...")
_run(
    [
        PYTHON,
        "-m",
        "utils.floorplan_fusion",
        "--walls",
        str(wall_dst),
        "--doors",
        str(placed_doors),
        "--geometry",
        str(geometry_json),
        "--out",
        str(fused_out),
    ],
    env=env,
)
shutil.copyfile(fused_out, legacy_fused_out)

print("[STEP 6b] Combined wall + door overlay...")
_run(
    [
        PYTHON,
        "-m",
        "utils.combined_overlay",
        "--image",
        str(image_path),
        "--walls",
        str(fused_out),
        "--doors",
        str(placed_doors),
        "--out",
        str(combined_overlay),
    ],
    env=env,
)

print("DONE")
