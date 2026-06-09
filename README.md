# Xaçmaz Weather

Fermerlər üçün çiləmə vaxtı köməkçisi. Sistem hava mənbələrindən saatlıq proqnoz yığır, Xaçmaz üçün konsensus hesablayır və külək/yağış şərtlərinə görə uyğun çiləmə pəncərələrini çıxarır.

## İndi nə var

- Gündəlik WhatsApp mesajı üçün `main.py`
- Mobil app və frontend üçün JSON backend: `api.py`
- Ortaq proqnoz servisi: `service.py`
- Konsensus və pəncərə məntiqi: `consensus.py`
- Hava mənbələri, o cümlədən Meteo.Az gateway və Gismeteo HTML inteqrasiyası: `fetchers.py`
- Lokal konfiqurasiya nümunəsi: `.env.example`

## Qurulum

```powershell
cd C:\Users\Admin\Desktop\xacmaz_weather
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` faylında API açarlarını və WhatsApp dəyərlərini doldurun. API açarları artıq Python fayllarında saxlanmır.

## Gündəlik WhatsApp işi

```powershell
python main.py
```

`python main.py` bir dəfə bütün məlumatları toplayır, record faylını saxlayır və dayanır. Artıq dayandırmaq üçün `Ctrl+C` lazım deyil.

Gündəlik 08:00 rejimi yenə lazımdırsa:

```powershell
python main.py --watch
```

WhatsApp göndərmədən yoxlamaq üçün:

```powershell
python main.py --no-whatsapp
```

`CALLMEBOT_APIKEY` və `CALLMEBOT_PHONE` boşdursa, mesaj WhatsApp-a göndərilməyəcək, test üçün konsola yazılacaq.

## Meteo.Az

Meteo.Az HTML scraping əvəzinə ETSN gateway endpoint-i ilə oxunur:

```text
https://gateway.etsn.az/api/prognosis/public-data
```

`.env` dəyərləri:

```text
METEO_AZ_CITY_ID=65
METEO_AZ_TYPE_ID=1
METEO_AZ_KEY_HEADER=etsn
METEO_AZ_VALUE_HEADER=...
METEO_AZ_WIND_UNIT=ms
```

Meteo.Az nəticəsi ayrıca Excel/CSV/JSON yaratmır. `fetch_meteo_az()` 7 günlük gündüz proqnozunu mobil app üçün saatlıq record-lara çevirib birbaşa return edir. Gündüz dəyərləri `PREFERRED_HOURS` saatlarına paylanır.

## Gismeteo

Gismeteo public API vermədiyi üçün `https://www.gismeteo.ru/weather-khachmaz-5284/3-days/` səhifəsinin server-rendered HTML forecast grid-i oxunur.

`.env` dəyəri:

```text
GISMETEO_URL=https://www.gismeteo.ru/weather-khachmaz-5284/3-days/
GISMETEO_TOMORROW_URL=https://www.gismeteo.ru/weather-khachmaz-5284/tomorrow/
```

`fetch_gismeteo()` və `fetch_gismeteo_tomorrow()` fayl yaratmır. `/3-days/` səhifəsindəki 4 periodlu forecast-u mobil app formatına çevirir:

- `Ночь` -> `00:00`
- `Утро` -> `06:00`
- `День` -> `12:00`
- `Вечер` -> `18:00`

`/tomorrow/` səhifəsi daha xırda vaxt slotları verir və saatları olduğu kimi saxlanır: məsələn `1:00`, `4:00`, `7:00`, `10:00`, `13:00`, `16:00`, `19:00`, `22:00`.

Gismeteo yağış ehtimalı yox, yağış miqdarı (`mm`) verdiyi üçün `precip_mm` ayrıca saxlanır və konsensus üçün sadə risk faizinə çevrilir: `0 => 0%`, `0.1-0.4 => 30%`, `0.5-1.9 => 60%`, `2+ => 85%`.

## Mobil app üçün API

```powershell
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Endpoint-lər:

- `GET /api/health`
- `GET /api/forecast`
- `GET /api/forecast?refresh=true`
- `GET /api/records?limit=7`
- `POST /api/advice`
- `POST /api/send-whatsapp`

Mobil app əsasən `/api/forecast` oxumalıdır. Cavabda `windows`, `hourly`, `successful_sources`, `failed_sources`, `thresholds` və WhatsApp üçün hazır `message` var.

## AI çiləmə məsləhəti

AI analiz üçün `.env` dəyərləri:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=medium
AI_ANALYSIS_DAYS=3
AI_MIN_WINDOW_HOURS=3
```

`POST /api/advice` hər dəfə çağırılanda mənbələrdən təzə hava datası yığılır, minimum 3 saatlıq və yaxın 3 günlük pəncərələr hazırlanır, OpenAI-dən sadə Azərbaycan dilində aqronom məsləhəti alınır.

Nümunə:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/advice `
  -ContentType 'application/json' `
  -Body '{"active_substance":"captan","crop":"şaftalı/gilas"}'
```

WhatsApp mesajı göndərmək:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/send-whatsapp `
  -ContentType 'application/json' `
  -Body '{"message":"AI-nin whatsapp_summary mətni","phone":""}'
```

`phone` boşdursa `.env`-dəki əsas nömrəyə göndərilir. Fermer öz nömrəsini yazarsa həmin nömrəyə göndərilir.

## Test

```powershell
python -m unittest
python -m compileall .
```

## Növbəti mobil mərhələ

Birinci mobil ekranlar:

- Bu gün çiləmə olar/olmaz statusu
- Ən uyğun saat pəncərələri
- Külək və yağış riski
- 5 günlük saatlıq proqnoz
- Mənbə etibarlılığı
- Push notification: səhər 08:00 yenilənmə
