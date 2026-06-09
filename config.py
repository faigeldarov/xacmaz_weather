"""
XAÇMAZ ÇİLƏMƏ KÖMƏKÇİSİ - Konfiqurasiya

API açarları və telefon nömrələri kodda saxlanmır. Lokal işlətmək üçün
.env.example faylını .env kimi kopyalayın və dəyərləri orada doldurun.
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RECORDS_DIR = BASE_DIR / "records"


def _load_local_env():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env_float(name, default):
    value = os.getenv(name)
    return float(value) if value not in (None, "") else default


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


def _env_hours(name, default):
    value = os.getenv(name)
    if not value:
        return default
    return [int(part.strip()) for part in value.split(",") if part.strip()]


_load_local_env()

# Xaçmazın koordinatları
LATITUDE = _env_float("LATITUDE", 41.375480)
LONGITUDE = _env_float("LONGITUDE", 48.817978)
CITY_NAME = os.getenv("CITY_NAME", "Xaçmaz")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Baku")

# WhatsApp nömrəsi (ölkə kodu ilə)
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "")
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY", "")
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE", WHATSAPP_NUMBER.replace("+", ""))

# OpenAI AI məsləhətçi parametrləri
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium")
AI_ANALYSIS_DAYS = _env_int("AI_ANALYSIS_DAYS", 3)
AI_MIN_WINDOW_HOURS = _env_int("AI_MIN_WINDOW_HOURS", 3)

# Çiləmə üçün hədd dəyərləri
MAX_WIND_SPEED_KMH = _env_float("MAX_WIND_SPEED_KMH", 15)       # küləyin maksimum sürəti (km/s)
MAX_PRECIP_PROBABILITY = _env_float("MAX_PRECIP_PROBABILITY", 30)   # yağış ehtimalının maksimumu (%)
MIN_WINDOW_DURATION_HOURS = _env_int("MIN_WINDOW_DURATION_HOURS", 1) # minimum açıq pəncərə müddəti (saat)
PREFERRED_HOURS = _env_hours("PREFERRED_HOURS", list(range(6, 21)))  # 06:00 - 20:00 arası baxılır

# API açarları (qeydiyyatdan sonra buraya əlavə edin)
API_KEYS = {
    "openweathermap": os.getenv("OPENWEATHERMAP_API_KEY", ""),
    "weatherapi": os.getenv("WEATHERAPI_API_KEY", ""),
    "tomorrow_io": os.getenv("TOMORROW_IO_API_KEY", ""),
    "meteoblue": os.getenv("METEOBLUE_API_KEY", ""),
}

# Meteo.Az gateway parametrləri
METEO_AZ_BASE_URL = os.getenv("METEO_AZ_BASE_URL", "https://gateway.etsn.az/api/prognosis/public-data")
METEO_AZ_CITY_ID = _env_int("METEO_AZ_CITY_ID", 65)
METEO_AZ_TYPE_ID = _env_int("METEO_AZ_TYPE_ID", 1)
METEO_AZ_KEY_HEADER = os.getenv("METEO_AZ_KEY_HEADER", "etsn")
METEO_AZ_VALUE_HEADER = os.getenv("METEO_AZ_VALUE_HEADER", "")
METEO_AZ_WIND_UNIT = os.getenv("METEO_AZ_WIND_UNIT", "ms").lower()

# Gismeteo public HTML mənbəyi
GISMETEO_URL = os.getenv("GISMETEO_URL", "https://www.gismeteo.ru/weather-khachmaz-5284/3-days/")
GISMETEO_TOMORROW_URL = os.getenv("GISMETEO_TOMORROW_URL", "https://www.gismeteo.ru/weather-khachmaz-5284/tomorrow/")

# Mənbə çəkiləri (başlanğıc - zamanla ERA5 ilə yenilənəcək)
SOURCE_WEIGHTS = {
    "open_meteo": 1.0,
    "yr_no": 1.0,
    "openweathermap": 1.0,
    "weatherapi": 1.0,
    "tomorrow_io": 1.0,
    "meteoblue": 1.0,
    "meteo_az": 1.0,
    "gismeteo": 1.0,
    "gismeteo_tomorrow": 1.0,
}
