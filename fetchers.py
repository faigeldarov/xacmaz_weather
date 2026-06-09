"""
XAÇMAZ ÇİLƏMƏ KÖMƏKÇİSİ
Hava mənbələrindən data toplayan modul
"""

import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from bs4 import BeautifulSoup
from config import (
    LATITUDE, LONGITUDE, TIMEZONE, API_KEYS, PREFERRED_HOURS,
    METEO_AZ_BASE_URL, METEO_AZ_CITY_ID, METEO_AZ_TYPE_ID,
    METEO_AZ_KEY_HEADER, METEO_AZ_VALUE_HEADER, METEO_AZ_WIND_UNIT,
    GISMETEO_URL, GISMETEO_TOMORROW_URL,
)
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo(TIMEZONE)
METEO_AZ_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Mobile Safari/537.36"
)
GISMETEO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
GISMETEO_PERIOD_HOURS = {
    "Ночь": 0,
    "Утро": 6,
    "День": 12,
    "Вечер": 18,
}
RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
SECRET_QUERY_KEYS = {"key", "appid", "apikey", "api_key", "value"}


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

    body = response.text[:300] if response.text else ""
    return f"{response.status_code} error for {_redact_url(response.url)}; body: {body}"


def to_local_time_string(value):
    """
    API-lərdən gələn ISO/UTC vaxtlarını Bakı saatına çevirir.
    Sadə lokal formatlar olduğu kimi saxlanılır.
    """
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return text[:16].replace("T", " ")

    if dt.tzinfo is not None:
        dt = dt.astimezone(LOCAL_TZ)

    return dt.strftime("%Y-%m-%d %H:%M")


def _as_number(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    matches = re.findall(r"\d+(?:[.,]\d+)?", str(value))
    if not matches:
        return None

    numbers = [float(match.replace(",", ".")) for match in matches]
    return sum(numbers) / len(numbers)


def _as_int(value):
    number = _as_number(value)
    if number is None:
        return None
    return int(round(number))


def _wind_to_kmh(value, unit):
    wind = _as_number(value)
    if wind is None:
        return None
    if unit in {"ms", "m/s", "mps"}:
        return wind * 3.6
    return wind


def wind_direction_az(degree):
    degree = _as_number(degree)
    if degree is None:
        return ""

    directions = [
        "Şimal",
        "Şimal-şərq",
        "Şərq",
        "Cənub-şərq",
        "Cənub",
        "Cənub-qərb",
        "Qərb",
        "Şimal-qərb",
    ]
    return directions[round(degree / 45) % 8]


def _precip_mm_to_probability(precip_mm):
    precip_mm = _as_number(precip_mm)
    if precip_mm is None:
        return None
    if precip_mm <= 0:
        return 0
    if precip_mm < 0.5:
        return 30
    if precip_mm < 2:
        return 60
    return 85


def _row_text_values(soup, selector):
    row = soup.select_one(selector)
    if not row:
        return []
    return [" ".join(item.get_text(" ", strip=True).split()) for item in row.select(".row-item")]


def _chart_values(soup, selector, value_tag):
    row = soup.select_one(selector)
    if not row:
        return []
    return [_as_number(item.get("value")) for item in row.select(f"{value_tag}[value]")]


def _gismeteo_dates(date_items):
    year = datetime.now(LOCAL_TZ).year
    dates = []
    previous = None

    for text in date_items:
        match = re.search(r"(\d{1,2})\s+([а-яё]+)", text.lower())
        if not match:
            continue

        day = int(match.group(1))
        month = RU_MONTHS.get(match.group(2))
        if not month:
            continue

        candidate = datetime(year, month, day)
        if previous and candidate.date() < previous.date():
            year += 1
            candidate = datetime(year, month, day)

        dates.append(candidate)
        previous = candidate

    return dates


def _gismeteo_wind_records(soup):
    records = []
    for item in soup.select(".widget-row-wind .row-item"):
        speed_el = item.select_one(".wind-speed speed-value[value]")
        gust_el = item.select_one(".wind-gust speed-value[value]")
        direction_el = item.select_one(".wind-direction")
        records.append({
            "wind_kmh": (_as_number(speed_el.get("value")) * 3.6) if speed_el else None,
            "wind_gust_kmh": (_as_number(gust_el.get("value")) * 3.6) if gust_el else None,
            "wind_direction_ru": " ".join(direction_el.get_text(" ", strip=True).split()) if direction_el else "",
        })
    return records


def parse_gismeteo_html(html):
    soup = BeautifulSoup(html, "html.parser")

    date_texts = _row_text_values(soup, ".widget-row-tod-date")
    if not date_texts:
        date_texts = _row_text_values(soup, ".widget-row-datetime-date")
    period_texts = _row_text_values(soup, ".widget-row-datetime-time")
    dates = _gismeteo_dates(date_texts)

    temperatures = _chart_values(soup, ".widget-row-chart-temperature-air", "temperature-value")
    pressures = _chart_values(soup, ".widget-row-chart-pressure", "pressure-value")
    humidity_values = [_as_number(value) for value in _row_text_values(soup, ".widget-row-humidity")]
    precip_mm_values = [_as_number(value) for value in _row_text_values(soup, ".widget-row-precipitation-bars")]
    wind_records = _gismeteo_wind_records(soup)
    icon_titles = [
        item.select_one("[data-tooltip]").get("data-tooltip", "")
        if item.select_one("[data-tooltip]") else ""
        for item in soup.select(".widget-row-icon .row-item")
    ]

    slot_count = min(
        len(period_texts),
        len(temperatures),
        len(wind_records),
        len(precip_mm_values),
        len(humidity_values),
    )
    if not dates or slot_count == 0:
        return []

    records = []
    for index in range(slot_count):
        period = period_texts[index]
        time_match = re.search(r"(\d{1,2}):(\d{2})", period)

        if time_match:
            if not dates:
                break
            dt = dates[min(index // max(len(period_texts), 1), len(dates) - 1)]
            dt = dt.replace(hour=int(time_match.group(1)), minute=int(time_match.group(2)))
        else:
            date_index = index // 4
            if date_index >= len(dates):
                break
            hour = GISMETEO_PERIOD_HOURS.get(period)
            if hour is None:
                continue
            dt = dates[date_index] + timedelta(hours=hour)

        precip_mm = precip_mm_values[index]
        wind = wind_records[index]
        records.append({
            "datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "temperature": temperatures[index],
            "wind_kmh": wind["wind_kmh"],
            "precip_prob": _precip_mm_to_probability(precip_mm),
            "humidity": humidity_values[index],
            "pressure": pressures[index] if index < len(pressures) else None,
            "precip_mm": precip_mm,
            "wind_gust_kmh": wind["wind_gust_kmh"],
            "wind_direction_ru": wind["wind_direction_ru"],
            "period_ru": period,
            "weather_event": icon_titles[index] if index < len(icon_titles) else "",
            "source_note": "gismeteo public html",
        })

    return records


def _date_from_forecast_start(value):
    text = str(value or "")
    if len(text) >= 10:
        return text[:10]
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")


def _meteo_az_item_to_hourly(city_name, forecast_type, item):
    forecast_date = datetime.strptime(_date_from_forecast_start(item.get("start_at")), "%Y-%m-%d")
    wind_kmh = _wind_to_kmh(item.get("wind_speed"), METEO_AZ_WIND_UNIT)
    precip_prob = _as_number(item.get("precip_prob"))
    temperature = _as_number(item.get("temp"))
    humidity = _as_number(item.get("humidity"))

    if wind_kmh is None:
        wind_kmh = 0
    if precip_prob is None:
        precip_prob = 0

    records = []
    for hour in PREFERRED_HOURS:
        dt = forecast_date + timedelta(hours=hour)
        records.append({
            "datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "temperature": temperature,
            "wind_kmh": wind_kmh,
            "precip_prob": precip_prob,
            "humidity": humidity,
            "source_note": "meteo.az gateway (gündüz proqnozu)",
            "city": city_name,
            "forecast_type": forecast_type,
            "weather_event_day": item.get("icon_name"),
            "weather_event_night": item.get("icon_name_night"),
            "wind_dir": item.get("wind_dir"),
            "wind_direction": wind_direction_az(item.get("wind_dir")),
            "created_at": item.get("created_at"),
        })
    return records


def fetch_open_meteo():
    """
    Open-Meteo - Tamamilə pulsuz, açar lazım deyil
    Saatlıq: temp, yağış ehtimalı, külək, rütubət
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,relative_humidity_2m",
            "forecast_days": 5,
            "timezone": TIMEZONE,
            "windspeed_unit": "kmh"
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        hourly = data["hourly"]
        wind_values = hourly.get("wind_speed_10m") or hourly.get("windspeed_10m")
        humidity_values = hourly.get("relative_humidity_2m") or hourly.get("relativehumidity_2m")
        result = []
        for i, time_str in enumerate(hourly["time"]):
            result.append({
                "datetime": time_str,
                "temperature": hourly["temperature_2m"][i],
                "wind_kmh": wind_values[i],
                "precip_prob": hourly["precipitation_probability"][i],
                "humidity": humidity_values[i],
            })
        log.info(f"Open-Meteo: {len(result)} saat məlumat alındı")
        return result
    except Exception as e:
        log.error(f"Open-Meteo xətası: {_safe_request_error(e)}")
        return None


def fetch_yr_no():
    """
    Yr.no - Norveç Meteoroloji İdarəsi, pulsuz
    Çox dəqiq Avropa modeli
    """
    try:
        url = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
        params = {"lat": LATITUDE, "lon": LONGITUDE}
        headers = {"User-Agent": "XacmazFarmerApp/1.0 farmer@xacmaz.az"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        result = []
        for item in data["properties"]["timeseries"][:120]:  # 5 gün = 120 saat
            details = item["data"]["instant"]["details"]
            next1h = item["data"].get("next_1_hours", {})
            precip_prob = next1h.get("details", {}).get("probability_of_precipitation", 0)

            result.append({
                "datetime": to_local_time_string(item["time"]),
                "temperature": details.get("air_temperature"),
                "wind_kmh": details.get("wind_speed", 0) * 3.6,  # m/s → km/s
                "precip_prob": precip_prob,
                "humidity": details.get("relative_humidity"),
            })
        log.info(f"Yr.no: {len(result)} saat məlumat alındı")
        return result
    except Exception as e:
        log.error(f"Yr.no xətası: {_safe_request_error(e)}")
        return None


def fetch_openweathermap():
    """
    OpenWeatherMap - 1000 sorğu/gün pulsuz
    API açarı: openweathermap.org/api
    """
    key = API_KEYS.get("openweathermap")
    if not key or key == "BURAYA_AÇARINIZI_YAZIN":
        log.warning("OpenWeatherMap açarı yoxdur, keçilir")
        return None
    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": LATITUDE,
            "lon": LONGITUDE,
            "appid": key,
            "units": "metric",
            "cnt": 40  # 5 gün * 8 (hər 3 saatdan bir)
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        result = []
        for item in data["list"]:
            dt = datetime.fromtimestamp(item["dt"], LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
            result.append({
                "datetime": dt,
                "temperature": item["main"]["temp"],
                "wind_kmh": item["wind"]["speed"] * 3.6,
                "precip_prob": item.get("pop", 0) * 100,
                "humidity": item["main"]["humidity"],
            })
        log.info(f"OpenWeatherMap: {len(result)} nöqtə alındı")
        return result
    except Exception as e:
        log.error(f"OpenWeatherMap xətası: {_safe_request_error(e)}")
        return None


def fetch_weatherapi():
    """
    WeatherAPI.com - 1M sorğu/ay pulsuz
    API açarı: weatherapi.com
    """
    key = API_KEYS.get("weatherapi")
    if not key or key == "BURAYA_AÇARINIZI_YAZIN":
        log.warning("WeatherAPI açarı yoxdur, keçilir")
        return None
    try:
        url = "https://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": key,
            "q": f"{LATITUDE},{LONGITUDE}",
            "days": 5,
            "aqi": "no",
            "alerts": "no"
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        result = []
        for day in data["forecast"]["forecastday"]:
            for hour in day["hour"]:
                result.append({
                    "datetime": hour["time"],
                    "temperature": hour["temp_c"],
                    "wind_kmh": hour["wind_kph"],
                    "precip_prob": hour["chance_of_rain"],
                    "humidity": hour["humidity"],
                })
        log.info(f"WeatherAPI: {len(result)} saat alındı")
        return result
    except Exception as e:
        log.error(f"WeatherAPI xətası: {_safe_request_error(e)}")
        return None


def fetch_tomorrow_io():
    """
    Tomorrow.io - 500 sorğu/gün pulsuz
    API açarı: tomorrow.io
    """
    key = API_KEYS.get("tomorrow_io")
    if not key or key == "BURAYA_AÇARINIZI_YAZIN":
        log.warning("Tomorrow.io açarı yoxdur, keçilir")
        return None
    try:
        url = "https://api.tomorrow.io/v4/weather/forecast"
        params = {
            "location": f"{LATITUDE},{LONGITUDE}",
            "apikey": key,
            "timesteps": "1h",
            "units": "metric"
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        result = []
        for item in data["timelines"]["hourly"][:120]:
            vals = item["values"]
            result.append({
                "datetime": to_local_time_string(item["time"]),
                "temperature": vals.get("temperature"),
                "wind_kmh": vals.get("windSpeed", 0) * 3.6,
                "precip_prob": vals.get("precipitationProbability", 0),
                "humidity": vals.get("humidity"),
            })
        log.info(f"Tomorrow.io: {len(result)} saat alındı")
        return result
    except Exception as e:
        log.error(f"Tomorrow.io xətası: {_safe_request_error(e)}")
        return None


def fetch_meteoblue():
    """
    Meteoblue - Peyk məlumatları ilə güclü model
    API açarı: meteoblue.com/en/weather-api
    """
    key = API_KEYS.get("meteoblue")
    if not key or key == "BURAYA_AÇARINIZI_YAZIN":
        log.warning("Meteoblue açarı yoxdur, keçilir")
        return None
    try:
        url = "https://my.meteoblue.com/packages/basic-1h"
        params = {
            "apikey": key,
            "lat": LATITUDE,
            "lon": LONGITUDE,
            "asl": 5,
            "format": "json",
            "forecast_days": 5
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        times = data["data_1h"]["time"]
        result = []
        for i, t in enumerate(times):
            result.append({
                "datetime": to_local_time_string(t),
                "temperature": data["data_1h"]["temperature"][i],
                "wind_kmh": data["data_1h"]["windspeed"][i],
                "precip_prob": data["data_1h"]["precipitation_probability"][i],
                "humidity": data["data_1h"]["relativehumidity"][i],
            })
        log.info(f"Meteoblue: {len(result)} saat alındı")
        return result
    except Exception as e:
        log.error(f"Meteoblue xətası: {_safe_request_error(e)}")
        return None


def fetch_meteo_az():
    """
    meteo.az - Azərbaycan Milli Meteorologiya xidməti
    ETSN gateway sorğusu ilə data çəkilir və saatlıq formata çevrilir.
    """
    if not METEO_AZ_VALUE_HEADER:
        log.warning("meteo.az gateway Value header yoxdur, keçilir")
        return None

    try:
        params = {
            "city_id": METEO_AZ_CITY_ID,
            "date": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d"),
            "type_id": METEO_AZ_TYPE_ID,
        }
        headers = {
            "User-Agent": METEO_AZ_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://map-meteoaz.etsn.az",
            "Referer": "https://map-meteoaz.etsn.az/",
            "Key": METEO_AZ_KEY_HEADER,
            "Value": METEO_AZ_VALUE_HEADER,
        }

        r = requests.get(METEO_AZ_BASE_URL, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        payload = data.get("data") or {}
        forecasts = payload.get("forecast") or []
        if not forecasts:
            log.warning("meteo.az gateway: data boş gəldi")
            return {"error": "DATA_BOS_GELDI", "source": "meteo.az"}

        city_name = (payload.get("city") or {}).get("name") or "Xaçmaz"
        forecast_type = (payload.get("type") or {}).get("name") or ""

        result = []
        for item in forecasts[:7]:
            result.extend(_meteo_az_item_to_hourly(city_name, forecast_type, item))

        log.info(f"meteo.az gateway: {len(result)} saatlıq məlumat alındı")
        return result

    except requests.RequestException as e:
        log.error(f"meteo.az gateway bağlantı xətası: {_safe_request_error(e)}")
        return {"error": str(e), "source": "meteo.az"}
    except Exception as e:
        log.error(f"meteo.az gateway gözlənilməz xəta: {e}")
        return {"error": str(e), "source": "meteo.az"}


def fetch_gismeteo():
    """
    Gismeteo public HTML forecast grid.
    API yoxdur; /3-days/ səhifəsindəki server-rendered forecast row-ları oxunur.
    """
    try:
        r = requests.get(GISMETEO_URL, headers=GISMETEO_HEADERS, timeout=30)
        r.raise_for_status()
        result = parse_gismeteo_html(r.text)

        if not result:
            log.warning("Gismeteo: forecast row-ları parse edilə bilmədi")
            return {"error": "DATA_TAPILMADI", "source": "gismeteo"}

        log.info(f"Gismeteo: {len(result)} period məlumat alındı")
        return result

    except requests.RequestException as e:
        log.error(f"Gismeteo bağlantı xətası: {_safe_request_error(e)}")
        return {"error": str(e), "source": "gismeteo"}


def fetch_gismeteo_tomorrow():
    """
    Gismeteo sabah səhifəsi. Daha xırda 3-saatlıq vaxt slotları verir.
    """
    try:
        r = requests.get(GISMETEO_TOMORROW_URL, headers=GISMETEO_HEADERS, timeout=30)
        r.raise_for_status()
        result = parse_gismeteo_html(r.text)

        if not result:
            log.warning("Gismeteo tomorrow: forecast row-ları parse edilə bilmədi")
            return {"error": "DATA_TAPILMADI", "source": "gismeteo_tomorrow"}

        for record in result:
            record["source_note"] = "gismeteo tomorrow public html"

        log.info(f"Gismeteo tomorrow: {len(result)} period məlumat alındı")
        return result

    except requests.RequestException as e:
        log.error(f"Gismeteo tomorrow bağlantı xətası: {_safe_request_error(e)}")
        return {"error": str(e), "source": "gismeteo_tomorrow"}
    except Exception as e:
        log.error(f"Gismeteo tomorrow gözlənilməz xəta: {e}")
        return {"error": str(e), "source": "gismeteo_tomorrow"}
    except Exception as e:
        log.error(f"Gismeteo gözlənilməz xəta: {e}")
        return {"error": str(e), "source": "gismeteo"}


def fetch_all_sources():
    """
    Bütün mənbələrdən data toplayan əsas funksiya
    """
    log.info("=== Bütün mənbələrdən data toplanır ===")

    sources = {
        "open_meteo": fetch_open_meteo(),
        "yr_no": fetch_yr_no(),
        "openweathermap": fetch_openweathermap(),
        "weatherapi": fetch_weatherapi(),
        "tomorrow_io": fetch_tomorrow_io(),
        "meteoblue": fetch_meteoblue(),
        "meteo_az": fetch_meteo_az(),
        "gismeteo": fetch_gismeteo(),
        "gismeteo_tomorrow": fetch_gismeteo_tomorrow(),
    }

    # Uğurlu və uğursuz mənbələri say
    successful = [k for k, v in sources.items() if v and not isinstance(v, dict)]
    failed = [k for k, v in sources.items() if not v or isinstance(v, dict)]

    # meteo.az xüsusi yoxlama
    if isinstance(sources.get("meteo_az"), dict) and "error" in sources["meteo_az"]:
        log.warning(f"⚠️  meteo.az problemi: {sources['meteo_az']['error']}")

    log.info(f"✅ Uğurlu mənbələr: {successful}")
    if failed:
        log.warning(f"❌ Uğursuz mənbələr: {failed}")

    return sources, successful, failed
