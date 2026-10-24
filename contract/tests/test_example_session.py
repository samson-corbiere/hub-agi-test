"""The example session is the shared fixture both app and backend test against.

These tests guarantee it is internally consistent: its meta.json matches the
schema, and every number it declares (sizes, hashes, counts, timestamps)
matches the actual files.
"""

import csv
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

CONTRACT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = CONTRACT_DIR / "meta.schema.json"
EXAMPLE_DIR = CONTRACT_DIR / "example-session"

IMU_HEADER = ["t_ns", "ax", "ay", "az", "gx", "gy", "gz"]
FRAMES_HEADER = ["frame_index", "t_ns"]


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def meta():
    return json.loads((EXAMPLE_DIR / "meta.json").read_text())


def read_rows(name, header):
    """Rows of an example CSV as strings, after checking its header."""
    with (EXAMPLE_DIR / name).open(newline="") as f:
        reader = csv.reader(f)
        assert next(reader) == header
        return list(reader)


def test_schema_is_a_valid_json_schema(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_example_meta_matches_schema(schema, meta):
    jsonschema.Draft202012Validator(schema).validate(meta)


def test_schema_rejects_unknown_file_names(schema, meta):
    bad = {**meta, "files": [*meta["files"], {"name": "evil.sh", "size": 1, "sha256": "0" * 64}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)


def test_schema_rejects_duplicate_file_names(schema, meta):
    video = next(f for f in meta["files"] if f["name"] == "video.mp4")
    bad = {**meta, "files": [video, {**video, "size": 1}, {**video, "size": 2}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)


def test_schema_rejects_missing_required_field(schema, meta):
    bad = {k: v for k, v in meta.items() if k != "video_start_t_ns"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)


def test_declared_files_exist_with_matching_size_and_sha256(meta):
    names = sorted(f["name"] for f in meta["files"])
    assert names == ["frames.csv", "imu.csv", "video.mp4"]
    for declared in meta["files"]:
        data = (EXAMPLE_DIR / declared["name"]).read_bytes()
        assert len(data) == declared["size"], declared["name"]
        assert hashlib.sha256(data).hexdigest() == declared["sha256"], declared["name"]


def test_frames_match_declared_video_range(meta):
    frames = read_rows("frames.csv", FRAMES_HEADER)
    assert len(frames) == meta["frame_count"]
    assert [int(index) for index, _ in frames] == list(range(len(frames)))
    times = [int(t_ns) for _, t_ns in frames]
    assert times == sorted(times)
    assert times[0] == meta["video_start_t_ns"]
    assert times[-1] == meta["video_end_t_ns"]


def test_imu_matches_declared_range_and_covers_video(meta):
    rows = read_rows("imu.csv", IMU_HEADER)
    assert len(rows) == meta["imu_sample_count"]
    times = [int(row[0]) for row in rows]
    assert times == sorted(times)
    assert times[0] == meta["imu_start_t_ns"]
    assert times[-1] == meta["imu_end_t_ns"]
    assert meta["imu_start_t_ns"] < meta["video_start_t_ns"]
    assert meta["imu_end_t_ns"] > meta["video_end_t_ns"]
