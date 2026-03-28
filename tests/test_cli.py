from pathlib import Path

import pytest

from hyroxanim.cli import build_parser, run_command


def test_run_synth_pipeline_writes_outputs(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run-synth-pipeline",
            "--n-athletes",
            "2",
            "--seed",
            "13",
            "--raw-dir",
            str(tmp_path / "raw"),
            "--processed-dir",
            str(tmp_path / "processed"),
            "--dt",
            "1.0",
        ]
    )
    run_command(args)

    assert (tmp_path / "raw" / "course.json").exists()
    assert (tmp_path / "raw" / "athlete_splits.json").exists()
    assert (tmp_path / "processed" / "trajectories.csv").exists()
    assert (tmp_path / "processed" / "trajectories.json").exists()


def test_process_synth_raises_with_missing_input_files(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "process-synth",
            "--course-path",
            str(tmp_path / "missing-course.json"),
            "--splits-path",
            str(tmp_path / "missing-splits.json"),
            "--out-dir",
            str(tmp_path / "processed"),
        ]
    )

    with pytest.raises(FileNotFoundError, match="Course file not found"):
        run_command(args)


def test_animate_parser_supports_decoration_toggle() -> None:
    parser = build_parser()
    args = parser.parse_args(["animate", "--no-decorations"])
    assert args.show_decorations is False
