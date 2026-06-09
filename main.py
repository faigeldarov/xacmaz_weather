"""
XAÇMAZ ÇİLƏMƏ KÖMƏKÇİSİ
Əsas proqram - məlumat toplama, WhatsApp göndərmə və opsional gündəlik cədvəl
"""

import argparse
import json
import sys
from fetchers import fetch_all_sources
from consensus import local_now, run_consensus
from config import CALLMEBOT_APIKEY, CALLMEBOT_PHONE, RECORDS_DIR
import logging


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("xacmaz_weather.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Xaçmaz çiləmə proqnozunu yığ və nəticəni çıxar.")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Proqramı açıq saxla və hər gün 08:00-da avtomatik işlə.",
    )
    parser.add_argument(
        "--no-whatsapp",
        action="store_true",
        help="WhatsApp göndərmə, mesajı yalnız konsola və record faylına yaz.",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="AI aqronom məsləhəti hazırla. Aktiv maddə verilməyibsə, proqram soruşacaq.",
    )
    parser.add_argument(
        "--active-substance",
        default="",
        help="AI analiz üçün aktiv maddə. Məsələn: captan",
    )
    parser.add_argument(
        "--crop",
        default="şaftalı/gilas",
        help="Bitki adı. Default: şaftalı/gilas",
    )
    parser.add_argument(
        "--send-ai-whatsapp",
        action="store_true",
        help="AI-nin qısa WhatsApp mesajını göndər.",
    )
    parser.add_argument(
        "--phone",
        default="",
        help="WhatsApp üçün əlavə nömrə. Boşdursa .env-dəki əsas nömrə istifadə olunur.",
    )
    return parser.parse_args()

# ============================================================
# WHATSAPP GÖNDƏRİCİ
# ============================================================

def send_whatsapp(message: str, phone: str = ""):
    """
    WhatsApp-a mesaj göndərir.
    
    2 variant var - hansını seçdiyini aşağıda müəyyən et:
    
    VARIANT A: CallMeBot (tamamilə pulsuz)
    ----------------------------------------
    Qeydiyyat: https://www.callmebot.com/blog/free-api-whatsapp-messages/
    1. WhatsApp-da +34 644 65 79 98 nömrəsinə "I allow callmebot to send me messages" yaz
    2. Sənə API açarı gələcək
    3. .env faylında CALLMEBOT_APIKEY və CALLMEBOT_PHONE dəyərlərini doldur
    
    VARIANT B: Twilio (aylıq $0.005/mesaj)
    ----------------------------------------
    twilio.com-da qeydiyyat
    """

    target_phone = (phone or CALLMEBOT_PHONE).replace("+", "").replace(" ", "")

    if CALLMEBOT_APIKEY and target_phone:
        try:
            import urllib.parse
            import requests
            encoded_msg = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone={target_phone}&text={encoded_msg}&apikey={CALLMEBOT_APIKEY}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                log.info("✅ WhatsApp mesajı göndərildi (CallMeBot)")
                return True
            else:
                log.error(f"CallMeBot xətası: {r.status_code} - {r.text}")
                return False
        except Exception as e:
            log.error(f"CallMeBot göndərmə xətası: {e}")
            return False

    # ---- KONSOLA YAZDIR (test üçün) ----
    log.info("=" * 60)
    log.info("WHATSAPP MESAJI (test rejimi):")
    log.info("=" * 60)
    print(message)
    log.info("=" * 60)
    return True


def save_daily_record(sources, windows, message, successful=None, failed=None):
    """
    Hər günün məlumatını saxla (accuracy tracking üçün)
    """
    now = local_now()
    today = now.strftime("%Y-%m-%d")
    record = {
        "date": today,
        "timestamp": now.isoformat(timespec="seconds"),
        "sources_requested": list(sources.keys()),
        "successful_sources": successful or [],
        "failed_sources": failed or [],
        "windows_found": len(windows),
        "message": message
    }

    RECORDS_DIR.mkdir(exist_ok=True)
    filepath = RECORDS_DIR / f"{today}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    log.info(f"Gün qeydi saxlandı: {filepath}")


def run_daily_job(send_message=True):
    """
    Əsas iş: mənbələrdən data topla, konsensus hesabla və record saxla.
    """
    log.info("=" * 60)
    log.info(f"Gündəlik iş başladı: {local_now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    # 1. Bütün mənbələrdən data topla
    sources, successful, failed = fetch_all_sources()

    if not successful:
        error_msg = "❌ Xaçmaz hava proqnozu: Heç bir mənbəyə qoşula bilmədim. İnternet bağlantısını yoxlayın."
        if send_message:
            send_whatsapp(error_msg)
        else:
            print(error_msg)
        return False

    # 2. Konsensus hesabla, pəncərələri tap
    message, windows, merged = run_consensus(sources, successful, failed)

    # 3. WhatsApp-a göndər
    if send_message:
        send_whatsapp(message)
    else:
        print(message)

    # 4. Qeydi saxla
    save_daily_record(sources, windows, message, successful, failed)

    log.info("Gündəlik iş tamamlandı")
    return True


def run_ai_advice(active_substance="", crop="şaftalı/gilas", send_message=False, phone=""):
    """
    AI aqronom məsləhəti: hava datasını yenidən yığır, yaxın 3 gün üçün ən uyğun
    minimum 3 saatlıq pəncərələri analiz edir.
    """
    from ai_advisor import generate_ai_advice

    active_substance = (active_substance or "").strip()
    if not active_substance:
        active_substance = input("Aktiv maddəni yazın: ").strip()

    if not active_substance:
        print("Aktiv maddə boş ola bilməz.")
        return False

    print("\n" + "=" * 60)
    print("AI ANALİZ HAZIRLANIR...")
    print("=" * 60 + "\n")

    result = generate_ai_advice(active_substance=active_substance, crop=crop)
    advice = result.get("advice") or result.get("fallback") or {}

    if not result.get("ok"):
        print("AI analizi tam alınmadı, fallback cavab göstərilir.")
        print(f"Səbəb: {result.get('error', 'Naməlum xəta')}")
        print()

    print("🌿 AI ÇİLƏMƏ MƏSLƏHƏTİ")
    print(f"Bitki: {crop}")
    print(f"Aktiv maddə: {active_substance}")
    print()
    print(advice.get("farmer_summary", "Məsləhət mətni alınmadı."))

    detailed_report = advice.get("detailed_report", "")
    if detailed_report:
        print()
        print("Ətraflı izah:")
        print(detailed_report)

    best = advice.get("best_window") or {}
    if best.get("available"):
        print()
        print("Ən uyğun pəncərə:")
        print(f"{best.get('start')} → {best.get('end')}")
        print(f"Uyğunluq: {best.get('score')}/100")
        print(best.get("reason", ""))

    warnings = advice.get("warnings") or []
    if warnings:
        print()
        print("Xəbərdarlıqlar:")
        for item in warnings:
            print(f"- {item}")

    whatsapp_summary = advice.get("whatsapp_summary", "")
    if whatsapp_summary:
        print()
        print("WhatsApp üçün qısa mesaj:")
        print(whatsapp_summary)

    if send_message and whatsapp_summary:
        send_whatsapp(whatsapp_summary, phone=phone)

    return bool(result.get("ok"))


# ============================================================
# ƏSAS PROQRAM
# ============================================================

if __name__ == "__main__":
    args = parse_args()

    log.info("🌿 Xaçmaz Çiləmə Köməkçisi başladı")

    if args.ai:
        run_ai_advice(
            active_substance=args.active_substance,
            crop=args.crop,
            send_message=args.send_ai_whatsapp and not args.no_whatsapp,
            phone=args.phone,
        )
        log.info("AI analiz tamamlandı və proqram dayandı")
    elif not args.watch:
        print("\n" + "="*60)
        print("MƏLUMATLAR TOPLANIR...")
        print("="*60 + "\n")
        run_daily_job(send_message=not args.no_whatsapp)
        log.info("Proqram tamamlandı və dayandı")
    else:
        import schedule
        import time

        log.info("Gündəlik cədvəl: hər səhər 08:00")
        run_daily_job(send_message=not args.no_whatsapp)
        schedule.every().day.at("08:00").do(run_daily_job, send_message=not args.no_whatsapp)

        log.info("Gözləmə rejimi: proqram hər gün 08:00-da işləyəcək")
        log.info("Dayandırmaq üçün: Ctrl+C")

        while True:
            schedule.run_pending()
            time.sleep(60)
