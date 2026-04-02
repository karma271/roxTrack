"""Command-line interface for hyroxanim."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hyroxanim.export.viewer import export_viewer_files
from hyroxanim.ingest.csv_convert import convert_real_csv_to_json
from hyroxanim.ingest.real import process_real_files
from hyroxanim.process.transform import transform_raw_files
from hyroxanim.synth.generate import generate_synthetic_dataset
from hyroxanim.viz.matplotlib_anim import animate_processed_trajectories


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(prog="hyroxanim", description="HYROX animation data tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate-synth", help="Generate synthetic raw data")
    generate_parser.add_argument("--n-athletes", type=int, default=5, help="Number of athletes")
    generate_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    generate_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/synth/raw"),
        help="Output directory for generated JSON",
    )

    process_parser = subparsers.add_parser(
        "process-synth",
        help="Transform synthetic raw data into processed trajectories",
    )
    process_parser.add_argument(
        "--course-path",
        type=Path,
        default=Path("data/synth/raw/course.json"),
        help="Path to raw course JSON",
    )
    process_parser.add_argument(
        "--splits-path",
        type=Path,
        default=Path("data/synth/raw/athlete_splits.json"),
        help="Path to raw athlete splits JSON",
    )
    process_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/synth/processed"),
        help="Output directory for processed files",
    )
    process_parser.add_argument(
        "--dt",
        type=float,
        default=1.0,
        help="Trajectory sampling interval",
    )
    process_real_parser = subparsers.add_parser(
        "process-real",
        help="Transform real race data into processed trajectories",
    )
    process_real_parser.add_argument(
        "--course-path",
        type=Path,
        default=Path("data/synth/raw/course.json"),
        help="Path to course JSON",
    )
    process_real_parser.add_argument(
        "--splits-path",
        type=Path,
        default=Path("data/real/raw/athlete_splits.json"),
        help="Path to real athlete splits JSON",
    )
    process_real_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/real/processed"),
        help="Output directory for processed files",
    )
    process_real_parser.add_argument(
        "--dt",
        type=float,
        default=1.0,
        help="Trajectory sampling interval",
    )
    process_real_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any athlete-level validation or transform error",
    )
    convert_real_csv_parser = subparsers.add_parser(
        "convert-real-csv",
        help="Convert flat real-race CSV splits to canonical JSON",
    )
    convert_real_csv_parser.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/real/raw/athlete_splits.csv"),
        help="Path to flat row-per-split CSV",
    )
    convert_real_csv_parser.add_argument(
        "--out-path",
        type=Path,
        default=Path("data/real/raw/athlete_splits.json"),
        help="Output JSON path",
    )
    convert_real_csv_parser.add_argument(
        "--no-normalize-start",
        action="store_true",
        help="Keep timestamps as provided instead of normalizing per athlete to start at zero",
    )
    export_viewer_parser = subparsers.add_parser(
        "export-viewer",
        help="Export compact viewer-ready JSON files",
    )
    export_viewer_parser.add_argument(
        "--course-path",
        type=Path,
        default=Path("data/synth/raw/course.json"),
        help="Path to course JSON",
    )
    export_viewer_parser.add_argument(
        "--trajectories-csv",
        type=Path,
        default=Path("data/synth/processed/trajectories.csv"),
        help="Path to processed trajectories CSV",
    )
    export_viewer_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/viewer"),
        help="Output directory for compact viewer JSON files",
    )

    animate_parser = subparsers.add_parser("animate", help="Animate processed trajectories")
    animate_parser.add_argument(
        "--course-path",
        type=Path,
        default=Path("data/synth/raw/course.json"),
        help="Path to raw course JSON",
    )
    animate_parser.add_argument(
        "--trajectories-csv",
        type=Path,
        default=Path("data/synth/processed/trajectories.csv"),
        help="Path to processed trajectories CSV",
    )
    animate_parser.add_argument(
        "--splits-path",
        type=Path,
        default=Path("data/synth/raw/athlete_splits.json"),
        help="Optional path to raw athlete splits JSON for station parking view",
    )
    animate_parser.add_argument(
        "--interval-ms",
        type=int,
        default=60,
        help="Animation frame interval in milliseconds",
    )
    animate_parser.add_argument(
        "--no-show",
        action="store_true",
        help="Build animation without opening a GUI window",
    )
    animate_parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional frame cap for quick smoke checks",
    )
    animate_parser.add_argument(
        "--show-decorations",
        dest="show_decorations",
        action="store_true",
        default=True,
        help="Render station labels and start/finish decoration boxes",
    )
    animate_parser.add_argument(
        "--no-decorations",
        dest="show_decorations",
        action="store_false",
        help="Disable station labels and start/finish decoration boxes",
    )

    pipeline_parser = subparsers.add_parser(
        "run-synth-pipeline",
        help="Generate + process synthetic data in one command",
    )
    pipeline_parser.add_argument("--n-athletes", type=int, default=5, help="Number of athletes")
    pipeline_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    pipeline_parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/synth/raw"),
        help="Output directory for generated raw JSON",
    )
    pipeline_parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/synth/processed"),
        help="Output directory for processed files",
    )
    pipeline_parser.add_argument(
        "--dt",
        type=float,
        default=1.0,
        help="Trajectory sampling interval",
    )
    pipeline_parser.add_argument(
        "--animate",
        action="store_true",
        help="Run animation after processing",
    )
    pipeline_parser.add_argument(
        "--no-show",
        action="store_true",
        help="When used with --animate, run headless without opening a window",
    )
    pipeline_parser.add_argument(
        "--interval-ms",
        type=int,
        default=60,
        help="Animation frame interval in milliseconds",
    )
    pipeline_parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional frame cap for quick smoke checks",
    )
    pipeline_parser.add_argument(
        "--show-decorations",
        dest="show_decorations",
        action="store_true",
        default=True,
        help="When used with --animate, render station/start/finish decorations",
    )
    pipeline_parser.add_argument(
        "--no-decorations",
        dest="show_decorations",
        action="store_false",
        help="When used with --animate, disable station/start/finish decorations",
    )
    return parser


def _require_file(path: Path, label: str, hint: str) -> None:
    """Validate that a required input file exists."""

    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}. {hint}")


def run_command(args: argparse.Namespace) -> None:
    """Execute a parsed CLI command."""

    if args.command == "generate-synth":
        output_paths = generate_synthetic_dataset(
            num_athletes=args.n_athletes,
            seed=args.seed,
            out_dir=args.out_dir,
        )
        print(f"Wrote course: {output_paths['course_path']}")
        print(f"Wrote athlete splits: {output_paths['splits_path']}")
    elif args.command == "process-synth":
        _require_file(
            args.course_path,
            "Course file",
            "Run `hyroxanim generate-synth` first or provide --course-path.",
        )
        _require_file(
            args.splits_path,
            "Splits file",
            "Run `hyroxanim generate-synth` first or provide --splits-path.",
        )

        output_paths = transform_raw_files(
            course_path=args.course_path,
            splits_path=args.splits_path,
            out_dir=args.out_dir,
            dt=args.dt,
        )
        print(f"Wrote trajectories CSV: {output_paths['csv_path']}")
        print(f"Wrote trajectories JSON: {output_paths['json_path']}")
    elif args.command == "process-real":
        _require_file(
            args.course_path,
            "Course file",
            "Provide --course-path to a valid course file.",
        )
        _require_file(
            args.splits_path,
            "Real splits file",
            "Provide --splits-path to a valid real splits file.",
        )
        result = process_real_files(
            course_path=args.course_path,
            splits_path=args.splits_path,
            out_dir=args.out_dir,
            dt=args.dt,
            strict=args.strict,
        )
        print(f"Wrote trajectories CSV: {result.output_paths['csv_path']}")
        print(f"Wrote trajectories JSON: {result.output_paths['json_path']}")
        print(f"Processed athletes: {result.processed_athletes}")
        print(f"Skipped athletes: {len(result.skipped_athletes)}")
        print(f"Total athletes: {result.total_athletes}")
        print(f"Warnings: {len(result.warnings)}")
        for warning in result.warnings:
            print(f"WARNING {warning.code}: {warning.message}")
        print(f"Errors: {len(result.errors)}")
        for error in result.errors:
            print(f"ERROR {error.code}: {error.message}")
    elif args.command == "convert-real-csv":
        _require_file(
            args.csv_path,
            "Real splits CSV",
            "Provide --csv-path to a valid CSV input file.",
        )
        result = convert_real_csv_to_json(
            csv_path=args.csv_path,
            out_path=args.out_path,
            normalize_start=not args.no_normalize_start,
        )
        print(f"Wrote real splits JSON: {result.out_path}")
        print(f"Athletes: {result.athlete_count}")
        print(f"Splits: {result.split_count}")
        print(f"Normalized start timestamps: {result.normalized_start}")
    elif args.command == "export-viewer":
        _require_file(
            args.course_path,
            "Course file",
            "Provide --course-path to a valid course file.",
        )
        _require_file(
            args.trajectories_csv,
            "Trajectories CSV",
            "Run `hyroxanim process-synth`/`process-real` first or provide --trajectories-csv.",
        )
        result = export_viewer_files(
            course_path=args.course_path,
            trajectories_csv=args.trajectories_csv,
            out_dir=args.out_dir,
        )
        print(f"Wrote viewer course JSON: {result.course_path}")
        print(f"Wrote viewer trajectories JSON: {result.trajectories_path}")
        print(f"Athletes: {result.athlete_count}")
        print(f"Points: {result.point_count}")
    elif args.command == "animate":
        _require_file(
            args.course_path,
            "Course file",
            "Run `hyroxanim generate-synth` first or provide --course-path.",
        )
        _require_file(
            args.trajectories_csv,
            "Trajectories CSV",
            "Run `hyroxanim process-synth` first or provide --trajectories-csv.",
        )
        if args.splits_path is not None:
            _require_file(
                args.splits_path,
                "Splits file",
                "Run `hyroxanim generate-synth` first or provide --splits-path.",
            )
        animate_processed_trajectories(
            course_path=args.course_path,
            trajectories_csv=args.trajectories_csv,
            splits_path=args.splits_path,
            interval_ms=args.interval_ms,
            no_show=args.no_show,
            max_frames=args.max_frames,
            show_decorations=args.show_decorations,
        )
        print("Animation completed.")
    elif args.command == "run-synth-pipeline":
        generated = generate_synthetic_dataset(
            num_athletes=args.n_athletes,
            seed=args.seed,
            out_dir=args.raw_dir,
        )
        print(f"Wrote course: {generated['course_path']}")
        print(f"Wrote athlete splits: {generated['splits_path']}")

        processed = transform_raw_files(
            course_path=generated["course_path"],
            splits_path=generated["splits_path"],
            out_dir=args.processed_dir,
            dt=args.dt,
        )
        print(f"Wrote trajectories CSV: {processed['csv_path']}")
        print(f"Wrote trajectories JSON: {processed['json_path']}")

        if args.animate:
            animate_processed_trajectories(
                course_path=generated["course_path"],
                trajectories_csv=processed["csv_path"],
                splits_path=generated["splits_path"],
                interval_ms=args.interval_ms,
                no_show=args.no_show,
                max_frames=args.max_frames,
                show_decorations=args.show_decorations,
            )
            print("Animation completed.")


def main() -> None:
    """Execute CLI command."""

    parser = build_parser()
    args = parser.parse_args()
    try:
        run_command(args)
    except (FileNotFoundError, ValueError) as exc:
        parser.print_usage(sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
