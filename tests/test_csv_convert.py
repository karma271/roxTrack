import csv
import json
from pathlib import Path

from hyroxanim.ingest.csv_convert import convert_real_csv_to_json


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["athlete_id", "sensor_type", "timestamp", "round"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_convert_real_csv_parses_mixed_timestamp_formats(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "splits.csv",
        [
            {
                "athlete_id": "athlete_001",
                "sensor_type": "start_tunnel_sensor",
                "timestamp": "01:00:00",
                "round": "",
            },
            {
                "athlete_id": "athlete_001",
                "sensor_type": "main_in_sensor",
                "timestamp": "3605.5",
                "round": "1",
            },
            {
                "athlete_id": "athlete_001",
                "sensor_type": "finish_line_sensor",
                "timestamp": "01:02:00",
                "round": "null",
            },
        ],
    )
    out_path = tmp_path / "out.json"

    result = convert_real_csv_to_json(csv_path=csv_path, out_path=out_path)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    splits = payload["athletes"][0]["splits"]

    assert result.athlete_count == 1
    assert result.split_count == 3
    assert splits[0]["timestamp"] == 0.0
    assert splits[1]["timestamp"] == 5.5
    assert splits[2]["timestamp"] == 120.0
    assert splits[0]["round"] is None
    assert splits[1]["round"] == 1
    assert splits[2]["round"] is None


def test_convert_real_csv_can_disable_normalization(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "splits.csv",
        [
            {
                "athlete_id": "athlete_001",
                "sensor_type": "start_tunnel_sensor",
                "timestamp": "100",
                "round": "",
            },
            {
                "athlete_id": "athlete_001",
                "sensor_type": "main_in_sensor",
                "timestamp": "130",
                "round": "1",
            },
        ],
    )
    out_path = tmp_path / "out.json"

    convert_real_csv_to_json(csv_path=csv_path, out_path=out_path, normalize_start=False)
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    splits = payload["athletes"][0]["splits"]
    assert splits[0]["timestamp"] == 100.0
    assert splits[1]["timestamp"] == 130.0
