#!/usr/bin/env python3
"""
Ingest OPC experiment CSV exports into InfluxDB.

Each CSV is expected to include a `timestamp` column followed by field columns.
Values are converted to boolean or floating point when possible; empty strings
are skipped. Data is written in batches to the configured InfluxDB bucket.
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence, Tuple

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 not supported here
    ZoneInfo = None  # type: ignore


DEFAULT_CSV_DIR = Path(os.getenv("OPC_CSV_DIR", "data/experiment_opc_log"))
DEFAULT_TIMESTAMP_FORMAT = os.getenv("OPC_TIMESTAMP_FORMAT", "%Y-%m-%d %H:%M:%S")
DEFAULT_TIMEZONE = os.getenv("OPC_TIMEZONE", "UTC")
DEFAULT_BATCH_SIZE = int(os.getenv("OPC_BATCH_SIZE", "500"))


@dataclass(frozen=True)
class Settings:
    url: str
    token: str
    org: str
    bucket: str
    measurement: str
    csv_dir: Path
    timestamp_format: str
    timezone_name: str
    batch_size: int


def parse_args() -> Settings:
    parser = argparse.ArgumentParser(
        description="Write OPC experiment CSV data to InfluxDB."
    )
    parser.add_argument(
        "--url",
        default=os.getenv("INFLUX_URL", "http://localhost:8086"),
        help="InfluxDB URL (default: %(default)s or INFLUX_URL env).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("INFLUX_TOKEN", "demo-token"),
        help="InfluxDB API token (default: %(default)s or INFLUX_TOKEN env).",
    )
    parser.add_argument(
        "--org",
        default=os.getenv("INFLUX_ORG", "demo-org"),
        help="InfluxDB organization (default: %(default)s or INFLUX_ORG env).",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("INFLUX_BUCKET", "demo-bucket"),
        help="InfluxDB bucket (default: %(default)s or INFLUX_BUCKET env).",
    )
    parser.add_argument(
        "--measurement",
        default=os.getenv("INFLUX_MEASUREMENT", "experiment_opc"),
        help=(
            "Measurement name used for all points "
            "(default: %(default)s or INFLUX_MEASUREMENT env)."
        ),
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=DEFAULT_CSV_DIR,
        help=f"Directory containing CSV files (default: {DEFAULT_CSV_DIR}).",
    )
    parser.add_argument(
        "--timestamp-format",
        default=DEFAULT_TIMESTAMP_FORMAT,
        help=(
            "datetime.strptime format string for the timestamp column "
            f"(default: {DEFAULT_TIMESTAMP_FORMAT!r})."
        ),
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=(
            "Timezone applied to naive timestamps. "
            "Use 'NAIVE' to keep timestamps as-is "
            f"(default: {DEFAULT_TIMEZONE!r})."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of points per write batch (default: {DEFAULT_BATCH_SIZE}).",
    )

    args = parser.parse_args()
    return Settings(
        url=args.url,
        token=args.token,
        org=args.org,
        bucket=args.bucket,
        measurement=args.measurement,
        csv_dir=args.csv_dir,
        timestamp_format=args.timestamp_format,
        timezone_name=args.timezone,
        batch_size=args.batch_size,
    )


def resolve_timezone(name: str) -> timezone | ZoneInfo | None:
    if not name or name.lower() == "naive":
        return None
    if name.upper() == "UTC":
        return timezone.utc
    if ZoneInfo is None:
        raise RuntimeError(
            "Time zone names other than 'UTC' require Python 3.9+ with zoneinfo."
        )
    try:
        return ZoneInfo(name)
    except Exception as exc:  # pragma: no cover - exceptional configuration path
        raise ValueError(f"Unknown time zone: {name}") from exc


def parse_timestamp(
    raw: str, fmt: str, tzinfo: timezone | ZoneInfo | None
) -> datetime:
    ts = datetime.strptime(raw, fmt)
    if tzinfo is None:
        return ts
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=tzinfo)
    return ts.astimezone(timezone.utc)


def parse_field_value(raw: str) -> bool | float | str | None:
    text = raw.strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return float(text)
    except ValueError:
        return text


def iter_points(
    files: Sequence[Path],
    measurement: str,
    timestamp_format: str,
    tzinfo: timezone | ZoneInfo | None,
) -> Iterator[Point]:
    for csv_path in files:
        with csv_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                continue
            for row_number, row in enumerate(reader, start=1):
                raw_timestamp = row.get("timestamp")
                if not raw_timestamp:
                    continue
                try:
                    timestamp = parse_timestamp(raw_timestamp, timestamp_format, tzinfo)
                except ValueError as exc:
                    raise ValueError(
                        f"Failed to parse timestamp {raw_timestamp!r} "
                        f"in {csv_path} at row {row_number}"
                    ) from exc

                point = Point(measurement).tag("source_file", csv_path.name).time(
                    timestamp
                )

                for field, raw_value in row.items():
                    if field == "timestamp":
                        continue
                    if raw_value is None:
                        continue
                    value = parse_field_value(raw_value)
                    if value is None:
                        continue
                    point.field(field, value)

                yield point


def locate_csv_files(directory: Path) -> Sequence[Path]:
    files = sorted(directory.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {directory}")
    return files


def write_points(
    client: InfluxDBClient,
    bucket: str,
    org: str,
    points: Iterable[Point],
    batch_size: int,
) -> Tuple[int, int]:
    write_api = client.write_api(write_options=SYNCHRONOUS)
    total_points = 0
    batches = 0
    batch: list[Point] = []

    for point in points:
        batch.append(point)
        if len(batch) >= batch_size:
            write_api.write(bucket=bucket, org=org, record=batch)
            total_points += len(batch)
            batches += 1
            batch.clear()

    if batch:
        write_api.write(bucket=bucket, org=org, record=batch)
        total_points += len(batch)
        batches += 1

    return total_points, batches


def main() -> None:
    settings = parse_args()
    timezone_info = resolve_timezone(settings.timezone_name)
    csv_files = locate_csv_files(settings.csv_dir)

    points = iter_points(
        csv_files, settings.measurement, settings.timestamp_format, timezone_info
    )

    with InfluxDBClient(
        url=settings.url, token=settings.token, org=settings.org, timeout=10_000
    ) as client:
        total_points, batches = write_points(
            client,
            bucket=settings.bucket,
            org=settings.org,
            points=points,
            batch_size=settings.batch_size,
        )

    file_count = len(csv_files)
    print(
        f"Wrote {total_points} points in {batches} batches "
        f"from {file_count} CSV file{'s' if file_count != 1 else ''} "
        f"to bucket={settings.bucket} org={settings.org} at {settings.url}"
    )


if __name__ == "__main__":
    main()

