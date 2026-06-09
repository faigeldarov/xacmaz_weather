"""
Xaçmaz Weather mobil app backend API.

İşə salmaq:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000
"""

import time

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_advisor import generate_ai_advice
from config import CITY_NAME
from main import send_whatsapp
from service import build_forecast_payload, load_recent_records


CACHE_SECONDS = 15 * 60
_cache = {
    "created_at": 0,
    "payload": None,
}

app = FastAPI(
    title="Xaçmaz Weather API",
    description="Fermerlər üçün çiləmə pəncərəsi proqnozu",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AdviceRequest(BaseModel):
    active_substance: str = Field(..., min_length=1, max_length=120)
    crop: str = Field("şaftalı/gilas", max_length=80)


class WhatsAppRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    phone: str = Field("", max_length=32)


def get_cached_forecast(refresh=False):
    now = time.time()
    if (
        not refresh
        and _cache["payload"] is not None
        and now - _cache["created_at"] < CACHE_SECONDS
    ):
        return _cache["payload"]

    payload = build_forecast_payload()
    _cache["payload"] = payload
    _cache["created_at"] = now
    return payload


@app.get("/")
def root():
    return {
        "name": "Xaçmaz Weather API",
        "city": CITY_NAME,
        "endpoints": [
            "/api/health",
            "/api/forecast",
            "/api/records",
        ],
    }


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "city": CITY_NAME,
        "cache_seconds": CACHE_SECONDS,
        "has_cached_forecast": _cache["payload"] is not None,
    }


@app.get("/api/forecast")
def forecast(refresh: bool = Query(False, description="Cache-i keç və mənbələrdən yenidən yığ")):
    return get_cached_forecast(refresh=refresh)


@app.get("/api/records")
def records(limit: int = Query(7, ge=1, le=60)):
    return {
        "ok": True,
        "records": load_recent_records(limit=limit),
    }


@app.post("/api/advice")
def advice(request: AdviceRequest):
    return generate_ai_advice(
        active_substance=request.active_substance.strip(),
        crop=request.crop.strip() or "şaftalı/gilas",
    )


@app.post("/api/send-whatsapp")
def send_whatsapp_message(request: WhatsAppRequest):
    sent = send_whatsapp(request.message, phone=request.phone)
    return {
        "ok": bool(sent),
        "sent": bool(sent),
        "target": "custom" if request.phone else "default",
    }
