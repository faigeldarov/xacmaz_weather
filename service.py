"""
Mobil app və bildirişlər üçün ortaq proqnoz servisi.
"""

from datetime import timedelta
import json

from config import (
    CITY_NAME, LATITUDE, LONGITUDE, TIMEZONE, RECORDS_DIR,
    MAX_WIND_SPEED_KMH, MAX_PRECIP_PROBABILITY,
    MIN_WINDOW_DURATION_HOURS, PREFERRED_HOURS,
)
from consensus import local_now, run_consensus
from fetchers import fetch_all_sources


def _confidence_from_source_count(source_count):
    if source_count >= 4:
        return "high"
    if source_count >= 2:
        return "medium"
    return "low"


def serialize_windows(windows):
    serialized = []
    for index, window in enumerate(windows, 1):
        start = window[0]["datetime"]
        end = window[-1]["datetime"] + timedelta(hours=1)
        avg_wind = round(sum(h["wind_kmh"] for h in window) / len(window), 1)
        avg_precip = round(sum(h["precip_prob"] for h in window) / len(window), 1)
        avg_sources = round(sum(h["source_count"] for h in window) / len(window))

        serialized.append({
            "index": index,
            "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"),
            "duration_hours": len(window),
            "avg_wind_kmh": avg_wind,
            "avg_precip_prob": avg_precip,
            "avg_source_count": avg_sources,
            "confidence": _confidence_from_source_count(avg_sources),
            "hours": [
                {
                    "datetime": hour["datetime"].isoformat(timespec="minutes"),
                    "wind_kmh": hour["wind_kmh"],
                    "precip_prob": hour["precip_prob"],
                    "source_count": hour["source_count"],
                    "wind_uncertainty": hour["wind_uncertainty"],
                    "precip_uncertainty": hour["precip_uncertainty"],
                }
                for hour in window
            ],
        })
    return serialized


def serialize_hourly(merged):
    return [
        {
            "datetime": item["datetime"],
            "wind_kmh": item["wind_kmh"],
            "precip_prob": item["precip_prob"],
            "temperature": item["temperature"],
            "humidity": item.get("humidity"),
            "pressure": item.get("pressure"),
            "precip_mm": item.get("precip_mm"),
            "source_count": item["source_count"],
            "sources": item["sources"],
            "wind_uncertainty": item["wind_uncertainty"],
            "precip_uncertainty": item["precip_uncertainty"],
        }
        for _, item in sorted(merged.items())
    ]


def build_forecast_payload():
    sources, successful, failed = fetch_all_sources()
    generated_at = local_now().isoformat(timespec="seconds")

    if not successful:
        return {
            "ok": False,
            "city": CITY_NAME,
            "location": {
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "timezone": TIMEZONE,
            },
            "generated_at": generated_at,
            "successful_sources": [],
            "failed_sources": failed,
            "windows": [],
            "hourly": [],
            "message": "Xaçmaz hava proqnozu: heç bir mənbəyə qoşula bilmədim.",
        }

    message, windows, merged = run_consensus(sources, successful, failed)
    return {
        "ok": True,
        "city": CITY_NAME,
        "location": {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "timezone": TIMEZONE,
        },
        "generated_at": generated_at,
        "thresholds": {
            "max_wind_speed_kmh": MAX_WIND_SPEED_KMH,
            "max_precip_probability": MAX_PRECIP_PROBABILITY,
            "min_window_duration_hours": MIN_WINDOW_DURATION_HOURS,
            "preferred_hours": PREFERRED_HOURS,
        },
        "successful_sources": successful,
        "failed_sources": failed,
        "windows": serialize_windows(windows),
        "hourly": serialize_hourly(merged),
        "message": message,
    }


def load_recent_records(limit=7):
    if not RECORDS_DIR.exists():
        return []

    records = []
    for path in sorted(RECORDS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records.append(record)
    return records
