"""
XAÇMAZ ÇİLƏMƏ KÖMƏKÇİSİ
Konsensus mühərriki - mənbələri birləşdirir, pəncərələri tapır
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
from config import (
    MAX_WIND_SPEED_KMH, MAX_PRECIP_PROBABILITY,
    MIN_WINDOW_DURATION_HOURS, PREFERRED_HOURS, SOURCE_WEIGHTS,
    TIMEZONE
)
import logging

log = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo(TIMEZONE)


def local_now():
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def normalize_datetime(dt_str):
    """Müxtəlif formatları standart formata çevirir"""
    if not dt_str:
        return None

    text = str(dt_str).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone(LOCAL_TZ).replace(tzinfo=None)
        return dt
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text[:16], fmt[:len(text[:16])])
        except ValueError:
            continue
    return None


def merge_hourly_data(sources, weights):
    """
    Bütün mənbələri saatlıq olaraq birləşdirir.
    Hər saat üçün çəkili ortalama hesablanır.
    """
    # Saata görə data topla
    hourly_data = defaultdict(lambda: {
        "wind_values": [], "precip_values": [], "temp_values": [],
        "humidity_values": [], "pressure_values": [], "precip_mm_values": [],
        "wind_weighted": 0, "precip_weighted": 0,
        "wind_weight": 0, "precip_weight": 0, "sources": []
    })

    for source_name, source_data in sources.items():
        if not source_data or isinstance(source_data, dict):
            continue

        weight = weights.get(source_name, 1.0)

        for record in source_data:
            dt_str = record.get("datetime", "")
            dt = normalize_datetime(dt_str)
            if not dt:
                continue

            # Saat açarı (dəqiqəsiz)
            hour_key = dt.strftime("%Y-%m-%d %H:00")

            wind = record.get("wind_kmh")
            precip = record.get("precip_prob")

            if wind is not None:
                hourly_data[hour_key]["wind_weighted"] += wind * weight
                hourly_data[hour_key]["wind_values"].append(wind)
                hourly_data[hour_key]["wind_weight"] += weight

            if precip is not None:
                hourly_data[hour_key]["precip_weighted"] += precip * weight
                hourly_data[hour_key]["precip_values"].append(precip)
                hourly_data[hour_key]["precip_weight"] += weight

            if record.get("temperature") is not None:
                hourly_data[hour_key]["temp_values"].append(record["temperature"])

            if record.get("humidity") is not None:
                hourly_data[hour_key]["humidity_values"].append(record["humidity"])

            if record.get("pressure") is not None:
                hourly_data[hour_key]["pressure_values"].append(record["pressure"])

            if record.get("precip_mm") is not None:
                hourly_data[hour_key]["precip_mm_values"].append(record["precip_mm"])

            if source_name not in hourly_data[hour_key]["sources"]:
                hourly_data[hour_key]["sources"].append(source_name)

    # Hər saat üçün konsensus hesabla
    merged = {}
    for hour_key, data in hourly_data.items():
        if data["wind_weight"] == 0:
            continue

        merged[hour_key] = {
            "datetime": hour_key,
            "wind_kmh": round(data["wind_weighted"] / data["wind_weight"], 1),
            "precip_prob": round(
                data["precip_weighted"] / data["precip_weight"]
                if data["precip_weight"] else 0, 1
            ),
            "temperature": round(
                sum(data["temp_values"]) / len(data["temp_values"])
                if data["temp_values"] else 0, 1
            ),
            "humidity": round(
                sum(data["humidity_values"]) / len(data["humidity_values"])
                if data["humidity_values"] else 0, 1
            ),
            "pressure": round(
                sum(data["pressure_values"]) / len(data["pressure_values"])
                if data["pressure_values"] else 0, 1
            ),
            "precip_mm": round(
                sum(data["precip_mm_values"]) / len(data["precip_mm_values"])
                if data["precip_mm_values"] else 0, 2
            ),
            "source_count": len(data["sources"]),
            "sources": data["sources"],
            # Mənbələr arası fərq (yüksəkdirsə qeyri-müəyyənlik çoxdur)
            "wind_uncertainty": round(
                max(data["wind_values"]) - min(data["wind_values"])
                if len(data["wind_values"]) > 1 else 0, 1
            ),
            "precip_uncertainty": round(
                max(data["precip_values"]) - min(data["precip_values"])
                if len(data["precip_values"]) > 1 else 0, 1
            ),
        }

    return dict(sorted(merged.items()))


def find_spray_windows(merged_data):
    """
    Çiləmə üçün uyğun saat pəncərələrini tapır.
    
    Şərtlər:
    - Külək < MAX_WIND_SPEED_KMH
    - Yağış ehtimalı < MAX_PRECIP_PROBABILITY
    - Saat PREFERRED_HOURS içindədir
    - Minimum MIN_WINDOW_DURATION_HOURS davamlılıq
    """
    now = local_now()
    windows = []
    current_window = []

    sorted_hours = sorted(merged_data.keys())

    for hour_key in sorted_hours:
        data = merged_data[hour_key]
        dt = datetime.strptime(hour_key, "%Y-%m-%d %H:00")

        # Keçmiş saatları atla
        if dt < now:
            continue

        # 5 gündən uzağı atla
        if dt > now + timedelta(days=5):
            break

        hour_of_day = dt.hour
        wind_ok = data["wind_kmh"] <= MAX_WIND_SPEED_KMH
        precip_ok = data["precip_prob"] <= MAX_PRECIP_PROBABILITY
        hour_ok = hour_of_day in PREFERRED_HOURS

        if wind_ok and precip_ok and hour_ok:
            if current_window:
                previous_dt = current_window[-1]["datetime"]
                if dt != previous_dt + timedelta(hours=1):
                    if len(current_window) >= MIN_WINDOW_DURATION_HOURS:
                        windows.append(current_window)
                    current_window = []

            current_window.append({
                "datetime": dt,
                "wind_kmh": data["wind_kmh"],
                "precip_prob": data["precip_prob"],
                "source_count": data["source_count"],
                "wind_uncertainty": data["wind_uncertainty"],
                "precip_uncertainty": data["precip_uncertainty"],
            })
        else:
            # Pəncərə qırıldı - saxla əgər kifayət qədər uzundursa
            if len(current_window) >= MIN_WINDOW_DURATION_HOURS:
                windows.append(current_window)
            current_window = []

    # Son pəncərəni yoxla
    if len(current_window) >= MIN_WINDOW_DURATION_HOURS:
        windows.append(current_window)

    return windows


def format_windows_az(windows, successful_sources, failed_sources):
    """
    Tapılan pəncərələri Azərbaycanca formatla
    """
    az_months = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "İyun", 7: "İyul", 8: "Avqust",
        9: "Sentyabr", 10: "Oktyabr", 11: "Noyabr", 12: "Dekabr"
    }
    now = local_now()

    lines = []
    lines.append("🌿 *XAÇMAZ ÇİLƏMƏ KÖMƏKÇİSİ*")
    lines.append(f"📅 {now.strftime('%d')} {az_months[now.month]} {now.year}, saat 08:00")
    lines.append(f"📡 {len(successful_sources)} mənbədən məlumat alındı")
    lines.append("")

    if not windows:
        lines.append("🔴 *Növbəti 5 gün ərzində uyğun çiləmə pəncərəsi tapılmadı*")
        lines.append("")
        lines.append("Səbəblər: külək həddindən yüksəkdir və/və ya yağış ehtimalı çoxdur.")
    else:
        lines.append(f"✅ *{len(windows)} çiləmə pəncərəsi tapıldı:*")
        lines.append("")

        for i, window in enumerate(windows, 1):
            start = window[0]["datetime"]
            end = window[-1]["datetime"] + timedelta(hours=1)

            # Ortalama dəyərlər
            avg_wind = round(sum(h["wind_kmh"] for h in window) / len(window), 1)
            avg_precip = round(sum(h["precip_prob"] for h in window) / len(window), 1)
            duration = len(window)

            # Tarix formatı
            start_str = f"{start.day} {az_months[start.month]}, saat {start.strftime('%H:%M')}"
            end_str = f"{end.strftime('%H:%M')}" if start.date() == end.date() else \
                      f"{end.day} {az_months[end.month]}, saat {end.strftime('%H:%M')}"

            # Etibarlılıq qeydi
            avg_sources = round(sum(h["source_count"] for h in window) / len(window))
            confidence = "🟢 Yüksək" if avg_sources >= 4 else "🟡 Orta" if avg_sources >= 2 else "🟠 Aşağı"

            lines.append(f"*Pəncərə {i}:*")
            lines.append(f"🕐 {start_str} → {end_str} ({duration} saat)")
            lines.append(f"💨 Külək: ortalama {avg_wind} km/s")
            lines.append(f"🌧 Yağış ehtimalı: {avg_precip}%")
            lines.append(f"📊 Etibarlılıq: {confidence} ({avg_sources} mənbə)")
            lines.append("")

    # Xəbərdarlıqlar
    if failed_sources:
        meteo_az_failed = any("meteo_az" in str(s) for s in failed_sources)
        if meteo_az_failed:
            lines.append("⚠️ *meteo.az-dan məlumat alına bilmədi* (saytın strukturu dəyişmiş ola bilər)")
        other_failed = [s for s in failed_sources if s != "meteo_az"]
        if other_failed:
            lines.append(f"ℹ️ Əlaqə qurulmayan mənbələr: {', '.join(other_failed)}")

    lines.append("")
    lines.append("_Növbəti yenilənmə: sabah saat 08:00_")

    return "\n".join(lines)


def run_consensus(sources, successful, failed):
    """
    Əsas konsensus prosesi
    """
    log.info("Məlumatlar birləşdirilir...")
    merged = merge_hourly_data(sources, SOURCE_WEIGHTS)
    log.info(f"Cəmi {len(merged)} saatlıq konsensus nöqtəsi")

    log.info("Çiləmə pəncərələri axtarılır...")
    windows = find_spray_windows(merged)
    log.info(f"{len(windows)} pəncərə tapıldı")

    message = format_windows_az(windows, successful, failed)
    return message, windows, merged
