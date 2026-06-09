"""
AI əsaslı çiləmə məsləhətçisi.

Hava mənbələri və deterministik filter əvvəl işləyir; AI yalnız praktik fermer
dilində ən uyğun pəncərəni seçib izah edir.
"""

from datetime import datetime, timedelta
import json
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from config import (
    AI_ANALYSIS_DAYS,
    AI_MIN_WINDOW_HOURS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
)
from consensus import local_now
from service import build_forecast_payload


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
SECRET_QUERY_KEYS = {"key", "appid", "apikey", "api_key", "value"}


ADVICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ok": {"type": "boolean"},
        "decision": {"type": "string"},
        "analysis_period": {"type": "string"},
        "crop": {"type": "string"},
        "active_substance": {"type": "string"},
        "best_window": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "available": {"type": "boolean"},
                "rank": {"type": "integer"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "score": {"type": "integer"},
                "title": {"type": "string"},
                "reason": {"type": "string"},
                "cautions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["available", "rank", "start", "end", "score", "title", "reason", "cautions"],
        },
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rank": {"type": "integer"},
                    "start": {"type": "string"},
                    "end": {"type": "string"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["rank", "start", "end", "score", "reason"],
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "farmer_summary": {"type": "string"},
        "detailed_report": {"type": "string"},
        "whatsapp_summary": {"type": "string"},
        "practical_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "ok",
        "decision",
        "analysis_period",
        "crop",
        "active_substance",
        "best_window",
        "alternatives",
        "warnings",
        "farmer_summary",
        "detailed_report",
        "whatsapp_summary",
        "practical_notes",
    ],
}


def _parse_dt(value):
    return datetime.fromisoformat(str(value).replace(" ", "T"))


def _redact_url(url):
    if not url:
        return ""

    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, "***" if key.lower() in SECRET_QUERY_KEYS else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _safe_request_error(error):
    response = getattr(error, "response", None)
    if response is None:
        return str(error)
    body = response.text[:500] if response.text else ""
    return f"{response.status_code} error for {_redact_url(response.url)}; body: {body}"


def _avg(values, digits=1):
    clean = [value for value in values if value not in (None, "")]
    if not clean:
        return None
    return round(sum(clean) / len(clean), digits)


def _hourly_lookup(forecast_payload):
    lookup = {}
    for hour in forecast_payload.get("hourly", []):
        dt = _parse_dt(hour["datetime"])
        lookup[dt.strftime("%Y-%m-%dT%H:%M")] = hour
    return lookup


def _window_hourly_details(window, hourly):
    start = _parse_dt(window["start"])
    end = _parse_dt(window["end"])
    details = []
    current = start

    while current < end:
        key = current.strftime("%Y-%m-%dT%H:%M")
        if key in hourly:
            details.append(hourly[key])
        current += timedelta(hours=1)

    return details


def _summarize_window(window, hourly):
    details = _window_hourly_details(window, hourly)
    return {
        "index": window["index"],
        "start": window["start"],
        "end": window["end"],
        "duration_hours": window["duration_hours"],
        "avg_wind_kmh": window["avg_wind_kmh"],
        "avg_precip_prob": window["avg_precip_prob"],
        "avg_temperature_c": _avg([hour.get("temperature") for hour in details]),
        "avg_humidity": _avg([hour.get("humidity") for hour in details]),
        "avg_precip_mm": _avg([hour.get("precip_mm") for hour in details], digits=2),
        "avg_source_count": window["avg_source_count"],
        "confidence": window["confidence"],
        "max_wind_uncertainty": max((hour.get("wind_uncertainty") or 0 for hour in window.get("hours", [])), default=0),
        "max_precip_uncertainty": max((hour.get("precip_uncertainty") or 0 for hour in window.get("hours", [])), default=0),
    }


def build_ai_payload(active_substance, crop="şaftalı/gilas", forecast_payload=None):
    forecast_payload = forecast_payload or build_forecast_payload()
    now = local_now()
    end = (now.replace(hour=23, minute=59, second=59, microsecond=0) + timedelta(days=AI_ANALYSIS_DAYS - 1))
    hourly = _hourly_lookup(forecast_payload)

    candidate_windows = []
    too_short_windows = 0
    out_of_range_windows = 0

    for window in forecast_payload.get("windows", []):
        start = _parse_dt(window["start"])
        if start < now or start > end:
            out_of_range_windows += 1
            continue
        if window.get("duration_hours", 0) < AI_MIN_WINDOW_HOURS:
            too_short_windows += 1
            continue
        candidate_windows.append(_summarize_window(window, hourly))

    hourly_3_days = []
    for hour in forecast_payload.get("hourly", []):
        dt = _parse_dt(hour["datetime"])
        if now <= dt <= end:
            hourly_3_days.append({
                "datetime": hour["datetime"],
                "wind_kmh": hour.get("wind_kmh"),
                "precip_prob": hour.get("precip_prob"),
                "temperature": hour.get("temperature"),
                "humidity": hour.get("humidity"),
                "source_count": hour.get("source_count"),
            })

    return {
        "crop": crop,
        "active_substance": active_substance,
        "language": "az",
        "style": "praktik fermer dili, qısa və əsaslandırılmış",
        "analysis_days": AI_ANALYSIS_DAYS,
        "min_window_hours": AI_MIN_WINDOW_HOURS,
        "generated_at": forecast_payload.get("generated_at"),
        "successful_sources": forecast_payload.get("successful_sources", []),
        "failed_sources": forecast_payload.get("failed_sources", []),
        "candidate_windows": candidate_windows,
        "rejected_summary": {
            "too_short_windows": too_short_windows,
            "out_of_range_windows": out_of_range_windows,
            "total_raw_windows": len(forecast_payload.get("windows", [])),
        },
        "hourly_3_days": hourly_3_days[:90],
    }


def _system_prompt():
    return (
        "Sən Azərbaycan dilində danışan praktik aqronom məsləhətçisisən. "
        "Mövzu şaftalı və gilas bağlarında çiləmə vaxtının seçilməsidir. "
        "Fermer aktiv maddəni əl ilə yazır; əgər aktiv maddə barədə dəqiq əmin deyilsənsə, bunu de və ehtiyatlı yanaş. "
        "Sən dərmanın etiketini əvəz etmirsən; etiket qaydalarını üstün tutmağı xatırlat. "
        "Minimum praktik pəncərə 3 saatdır. Yaxın 3 gündə uyğun pəncərə yoxdursa, dərman vurmamağı tövsiyə et və əsas səbəbləri de. "
        "Çox isti saatları, yüksək küləyi, yağış riskini, şeh/rütubət ehtimalını və mənbə etibarlılığını nəzərə al. "
        "Cavab yalnız Azərbaycan dilində, fermerin anlayacağı sadə üslubda olsun. "
        "JSON sahələri fermerə faydalı olacaq qədər izahlı olsun: reason 3-5 cümlə, farmer_summary 5-7 cümlə, "
        "detailed_report app üçün 8-12 qısa cümləlik izah olsun. detailed_report içində niyə bu pəncərə yaxşıdır, "
        "niyə günorta və ya digər pəncərələr daha zəifdir, külək/yağış/temperatur/rütubət baxımından səbəbləri yaz. "
        "whatsapp_summary 6-8 qısa sətir olsun və yalnız nəticə yox, əsas səbəbləri də göstərsin."
    )


def _extract_response_text(data):
    if data.get("output_text"):
        return data["output_text"]

    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
            if content.get("type") == "refusal":
                raise RuntimeError(content.get("refusal") or "Model refused the request")

    raise RuntimeError("OpenAI response text tapılmadı")


def _repair_mojibake_text(value):
    if not isinstance(value, str):
        return value
    if not any(marker in value for marker in ("Ã", "É", "Ä", "Å", "Æ")):
        return value
    try:
        return value.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return value


def _repair_mojibake(value):
    if isinstance(value, dict):
        return {key: _repair_mojibake(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_repair_mojibake(item) for item in value]
    return _repair_mojibake_text(value)


def _compact_ai_payload(ai_payload):
    compact = dict(ai_payload)
    compact["hourly_3_days"] = [
        hour for hour in ai_payload.get("hourly_3_days", [])
        if hour.get("datetime", "")[11:13] in {"06", "09", "12", "15", "18", "21"}
    ][:40]
    return compact


def call_openai_advisor(ai_payload, compact=False):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY .env faylında yoxdur")

    payload_for_model = _compact_ai_payload(ai_payload) if compact else ai_payload
    request_body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": json.dumps(payload_for_model, ensure_ascii=False)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "spray_advice",
                "strict": True,
                "schema": ADVICE_SCHEMA,
            }
        },
        "max_output_tokens": 6000,
    }

    if OPENAI_REASONING_EFFORT:
        request_body["reasoning"] = {"effort": OPENAI_REASONING_EFFORT}

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=90,
    )

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(_safe_request_error(exc)) from exc

    data = response.json()
    if data.get("status") == "incomplete":
        details = data.get("incomplete_details") or {}
        raise RuntimeError(f"OpenAI cavabı yarımçıq qayıtdı: {details}")

    text = _extract_response_text(data)
    try:
        return _repair_mojibake(json.loads(text))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI JSON cavabı parse olunmadı: {exc}") from exc


def generate_ai_advice(active_substance, crop="şaftalı/gilas", forecast_payload=None):
    ai_payload = build_ai_payload(active_substance=active_substance, crop=crop, forecast_payload=forecast_payload)
    forecast_meta = {
        "generated_at": ai_payload["generated_at"],
        "successful_sources": ai_payload["successful_sources"],
        "failed_sources": ai_payload["failed_sources"],
        "candidate_window_count": len(ai_payload["candidate_windows"]),
    }

    try:
        try:
            advice = call_openai_advisor(ai_payload)
        except Exception:
            advice = call_openai_advisor(ai_payload, compact=True)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "input": {
                "active_substance": active_substance,
                "crop": crop,
                "analysis_days": AI_ANALYSIS_DAYS,
                "min_window_hours": AI_MIN_WINDOW_HOURS,
            },
            "forecast_meta": forecast_meta,
            "fallback": _fallback_advice(ai_payload),
        }

    return {
        "ok": True,
        "input": {
            "active_substance": active_substance,
            "crop": crop,
            "analysis_days": AI_ANALYSIS_DAYS,
            "min_window_hours": AI_MIN_WINDOW_HOURS,
        },
        "forecast_meta": forecast_meta,
        "advice": advice,
    }


def _fallback_advice(ai_payload):
    candidates = ai_payload.get("candidate_windows", [])
    if not candidates:
        return {
            "decision": "AI analizi alınmadı və yaxın 3 gündə minimum 3 saatlıq uyğun pəncərə görünmədi.",
            "farmer_summary": "Hazırda çiləmə üçün tələsmə. Külək, yağış və pəncərə müddətini yenidən yoxlamaq lazımdır.",
            "detailed_report": "AI analizi alınmadığı üçün yalnız qayda əsaslı ehtiyat cavabı göstərilir. Yaxın 3 gün üçün minimum 3 saatlıq sabit pəncərə görünmür. Bu halda dərmanı tələsik vurmaq praktik deyil. Külək, yağış və pəncərə müddəti yenidən yoxlanmalıdır. Hava mənbələri yenilənəndə analizi təkrar etmək daha doğru olar.",
            "whatsapp_summary": "Çiləmə tövsiyəsi: hələ tələsməyin.\nAI analizi alınmadı.\nYaxın 3 gündə minimum 3 saatlıq uyğun pəncərə görünmür.\nKülək və yağış riskini yenidən yoxlayın.\nHava yenilənəndə təkrar analiz edin.",
        }

    best = sorted(
        candidates,
        key=lambda item: (
            item.get("avg_precip_prob") or 0,
            item.get("avg_wind_kmh") or 0,
            -(item.get("duration_hours") or 0),
        ),
    )[0]
    return {
        "decision": "AI analizi alınmadı, amma qayda əsaslı ən yaxşı pəncərə seçildi.",
        "farmer_summary": f"Ən uyğun namizəd: {best['start']} - {best['end']}. Külək ortalama {best['avg_wind_kmh']} km/s, yağış riski {best['avg_precip_prob']}%.",
        "detailed_report": f"AI analizi alınmadığı üçün qayda əsaslı seçim göstərilir. Ən uyğun namizəd {best['start']} - {best['end']} aralığıdır. Bu pəncərə minimum {AI_MIN_WINDOW_HOURS} saat tələbini ödəyir. Külək ortalama {best['avg_wind_kmh']} km/s-dir. Yağış riski {best['avg_precip_prob']}% görünür. Sahədə real küləyi və yarpaq səthində şehi ayrıca yoxlamaq lazımdır.",
        "whatsapp_summary": f"Çiləmə üçün namizəd vaxt: {best['start']} - {best['end']}.\nKülək: {best['avg_wind_kmh']} km/s.\nYağış riski: {best['avg_precip_prob']}%.\nMinimum {AI_MIN_WINDOW_HOURS} saatlıq pəncərə var.\nAI analizi alınmadı, qayda əsaslı seçimdir.\nSahədə külək və şehi yoxlayın.",
    }
