import argparse
import os
import sys
from contextlib import contextmanager


@contextmanager
def _patched_argv(new_argv):
    old_argv = sys.argv
    sys.argv = new_argv
    try:
        yield
    finally:
        sys.argv = old_argv


def _run_stage(stage_name, func, argv):
    print("\n" + "#" * 72)
    print(f"Running {stage_name} ...")
    print("#" * 72)
    with _patched_argv(argv):
        func()


def main():
    parser = argparse.ArgumentParser(
        description="Run the Sketch2FloorPlan pipeline (stage0 -> stage5)."
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        default=None,
        help="Path to the input floorplan image (used by stage0 and stage1). If omitted, you'll be prompted.",
    )
    args = parser.parse_args()

    raw_image_path = args.image_path
    if not raw_image_path:
        while True:
            raw_image_path = input("Enter image path: ").strip().strip('"').strip("'")
            if raw_image_path:
                break

    image_path = os.path.abspath(raw_image_path)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    # Ensure relative paths inside stages resolve consistently
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    import stage0
    import stage1_preprocess
    import stage2_line_detection
    import stage3_wall_graph
    import stage4_room_detection
    import stage5_architectural_cleanup

    _run_stage("Stage 0", stage0.main, ["stage0.py", image_path])
    _run_stage("Stage 1", stage1_preprocess.main, ["stage1_preprocess.py", image_path])

    # Stage 2/3 accept optional argv; passing only script name uses defaults.
    _run_stage("Stage 2", stage2_line_detection.main, ["stage2_line_detection.py"])
    _run_stage("Stage 3", stage3_wall_graph.main, ["stage3_wall_graph.py"])

    # Stage 4/5 do not require argv.
    _run_stage("Stage 4", stage4_room_detection.main, ["stage4_room_detection.py"])
    _run_stage("Stage 5", stage5_architectural_cleanup.main, ["stage5_architectural_cleanup.py"])

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
