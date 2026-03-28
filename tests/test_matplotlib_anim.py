from pathlib import Path

import matplotlib

from hyroxanim.process.transform import transform_raw_files
from hyroxanim.synth.generate import generate_synthetic_dataset
from hyroxanim.viz.matplotlib_anim import animate_processed_trajectories

matplotlib.use("Agg")


def test_matplotlib_animation_no_show_smoke(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    raw_paths = generate_synthetic_dataset(num_athletes=2, seed=4, out_dir=raw_dir)
    transform_raw_files(
        course_path=raw_paths["course_path"],
        splits_path=raw_paths["splits_path"],
        out_dir=processed_dir,
        dt=1.0,
    )

    animate_processed_trajectories(
        course_path=raw_paths["course_path"],
        trajectories_csv=processed_dir / "trajectories.csv",
        splits_path=raw_paths["splits_path"],
        no_show=True,
        max_frames=8,
    )
