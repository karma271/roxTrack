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


def test_process_real_raises_with_missing_input_files(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "process-real",
            "--course-path",
            str(tmp_path / "missing-course.json"),
            "--splits-path",
            str(tmp_path / "missing-real-splits.json"),
            "--out-dir",
            str(tmp_path / "processed"),
        ]
    )

    with pytest.raises(FileNotFoundError, match="Course file not found"):
        run_command(args)


def test_process_real_parser_supports_strict_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["process-real", "--strict"])
    assert args.strict is True


def test_convert_real_csv_parser_supports_normalize_toggle() -> None:
    parser = build_parser()
    args = parser.parse_args(["convert-real-csv", "--no-normalize-start"])
    assert args.no_normalize_start is True


def test_export_viewer_raises_with_missing_input_files(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "export-viewer",
            "--course-path",
            str(tmp_path / "missing-course.json"),
            "--trajectories-csv",
            str(tmp_path / "missing-trajectories.csv"),
            "--out-dir",
            str(tmp_path / "viewer"),
        ]
    )

    with pytest.raises(FileNotFoundError, match="Course file not found"):
        run_command(args)
