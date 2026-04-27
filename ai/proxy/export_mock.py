"""Mock export file generation: infer schema from real export file, write mock file, return mock path."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

from ai.proxy.mock_gen import generate_mock


def _read_json_for_schema(path: str) -> list | dict:
    """Load JSON from path; return list or dict for schema inference. Real data never returned to caller."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def _read_csv_for_schema(path: str) -> list[dict]:
    """Load CSV from path; return list of dicts (rows). Real data only used for schema."""
    rows: list[dict] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 100:
                break
            rows.append(dict(row))
    return rows


def _write_mock_json(mock_data: list | dict, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f, indent=2)


def _write_mock_csv(mock_rows: list[dict], out_path: str) -> None:
    if not mock_rows:
        return
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(mock_rows[0].keys()))
        writer.writeheader()
        writer.writerows(mock_rows)


def mock_export_file(
    real_path: str,
    file_format: str,
    study_id: str | None = None,
    row_limit: int = 50,
) -> str:
    """
    Read the real export file at real_path to infer schema, generate mock data,
    write to a new file, then remove the real file. Returns path to the mock file.
    Real file content is only used in memory for schema inference; it is deleted.
    """
    real_path = os.path.abspath(real_path)
    if not os.path.isfile(real_path):
        return real_path
    seed = hash(("qual_distribution_export", study_id or "")) % (2**31)
    mock_dir = Path(real_path).parent
    prefix = "mock_export_"
    fd, mock_path = tempfile.mkstemp(suffix=f".{file_format}", prefix=prefix, dir=str(mock_dir))
    os.close(fd)
    try:
        if file_format == "json":
            real_data = _read_json_for_schema(real_path)
            mock_data = generate_mock(real_data, row_limit=row_limit, seed=seed)
            _write_mock_json(mock_data, mock_path)
        else:
            real_rows = _read_csv_for_schema(real_path)
            if not real_rows:
                _write_mock_csv([], mock_path)
            else:
                mock_rows = generate_mock(real_rows, row_limit=row_limit, seed=seed)
                if isinstance(mock_rows, list):
                    _write_mock_csv(mock_rows, mock_path)
                else:
                    _write_mock_csv([], mock_path)
        try:
            os.remove(real_path)
        except OSError:
            pass
        return mock_path
    except Exception:
        try:
            os.remove(mock_path)
        except OSError:
            pass
        raise
