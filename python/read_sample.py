#!/usr/bin/env python3
"""
Fetch recent datapoints from InfluxDB using the Flux query language.

Requirements:
    pip install influxdb-client
"""

from __future__ import annotations

import os
from typing import Iterable

from influxdb_client import InfluxDBClient
from influxdb_client.client.flux_table import FluxRecord, FluxTable


def _iter_records(tables: Iterable[FluxTable]) -> Iterable[FluxRecord]:
    for table in tables:
        for record in table.records:
            yield record


def main() -> None:
    url = os.getenv("INFLUX_URL", "http://localhost:8086")
    token = os.getenv("INFLUX_TOKEN", "demo-token")
    org = os.getenv("INFLUX_ORG", "demo-org")
    bucket = os.getenv("INFLUX_BUCKET", "demo-bucket")
    measurement = os.getenv("INFLUX_MEASUREMENT", "cpu")
    field = os.getenv("INFLUX_FIELD", "usage_user")
    range_start = os.getenv("INFLUX_RANGE", "-1h")
    limit = int(os.getenv("INFLUX_LIMIT", "10"))

    flux = f"""
from(bucket: "{bucket}")
  |> range(start: {range_start})
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => r._field == "{field}")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
"""

    with InfluxDBClient(url=url, token=token, org=org, timeout=10_000) as client:
        query_api = client.query_api()
        tables = query_api.query(org=org, query=flux)

    records = list(_iter_records(tables))
    if not records:
        print("No data points found.")
        return

    print(
        f"Latest {len(records)} points for measurement={measurement} "
        f"field={field} in bucket={bucket} (org={org})"
    )
    for record in records:
        tags = ", ".join(
            f"{key}={value}"
            for key, value in record.values.items()
            if not key.startswith("_") and key not in {"result", "table"}
        )
        tag_str = f" {tags}" if tags else ""
        print(f"{record['_time']} value={record['_value']}{tag_str}")


if __name__ == "__main__":
    main()
