from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx


ICAT_BASE_URL = "https://icatplus.esrf.fr"
ICAT_PUBLIC_DATASETS_PATH = "/catalogue/public/datasets"
ICAT_PUBLIC_DATASETS_URL = ICAT_BASE_URL + ICAT_PUBLIC_DATASETS_PATH


def serialize_date_for_icat_query(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def serialize_datetime_for_query(value: datetime) -> str:
    serialized = value.isoformat()
    if value.tzinfo is not None and value.utcoffset() == timezone.utc.utcoffset(value):
        return serialized.replace("+00:00", "Z")
    return serialized


def build_icat_public_dataset_params(
    start_date: date | datetime,
    end_date: date | datetime,
    technique_pids: str | None,
    instrument_name: str | None,
) -> dict[str, str]:
    params = {
        "startDate": serialize_date_for_icat_query(start_date),
        "endDate": serialize_date_for_icat_query(end_date),
    }
    if technique_pids:
        params["techniquePids"] = technique_pids
    if instrument_name:
        params["instrumentName"] = instrument_name
    return params


def fetch_icat_public_datasets(
    start_date: date | datetime,
    end_date: date | datetime,
    technique_pids: str | None = None,
    instrument_name: str | None = None,
    client: httpx.Client | None = None,
) -> Any:
    close_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(
            ICAT_PUBLIC_DATASETS_URL,
            params=build_icat_public_dataset_params(
                start_date=start_date,
                end_date=end_date,
                technique_pids=technique_pids,
                instrument_name=instrument_name,
            ),
            headers={"accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    finally:
        if close_client:
            client.close()
