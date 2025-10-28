#!/usr/bin/env python3
"""
Simple example that writes a single CPU usage datapoint to InfluxDB.

Requirements:
    pip install influxdb-client
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timezone

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


def main() -> None:
    url = os.getenv("INFLUX_URL", "http://localhost:8086")
    token = os.getenv("INFLUX_TOKEN", "demo-token")
    org = os.getenv("INFLUX_ORG", "demo-org")
    bucket = os.getenv("INFLUX_BUCKET", "demo-bucket")

    measurement = os.getenv("INFLUX_MEASUREMENT", "cpu")
    host = os.getenv("INFLUX_HOST", "server01")
    usage = random.uniform(0, 100)

    point = (
        Point(measurement)
        .tag("host", host)
        .field("usage_user", usage)
        .time(datetime.now(timezone.utc))
    )

    with InfluxDBClient(url=url, token=token, org=org, timeout=10_000) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=bucket, org=org, record=point)

    print(
        f"Wrote point measurement={measurement} host={host} "
        f"usage_user={usage:.2f} to {bucket} (org={org}) at {url}"
    )


if __name__ == "__main__":
    main()
