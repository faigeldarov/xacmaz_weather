# Xaçmaz Çiləmə - normal mobil app üçün cloud quruluşu

Bu app-in normal telefon proqramı kimi işləməsi üçün Python backend kompüterdə yox, cloud serverdə işləməlidir.

## Niyə server lazımdır?

Telefon app sadəcə istifadəçi ekranıdır. Hava mənbələrindən məlumat yığmaq, Meteo.Az/Gismeteo scraping, OpenAI analizi və WhatsApp göndərişi backend-də işləyir.

API açarlarını APK içində saxlamaq olmaz. APK telefona düşəndən sonra açarlar çıxarıla bilər. Ona görə açarlar serverdə qalır.

## Tövsiyə olunan yol: Render

1. Render hesabı yarat: https://render.com
2. Bu layihəni GitHub reposuna yüklə.
3. Render-də `New +` -> `Blueprint` seç.
4. Repo olaraq bu layihəni seç.
5. Render `render.yaml` faylını görəcək və `xacmaz-weather-api` servisini yaradacaq.
6. Render səndən secret env dəyərlərini istəyəcək. Bunları `.env` faylındakı real dəyərlərlə doldur:

```text
OPENWEATHERMAP_API_KEY
WEATHERAPI_API_KEY
TOMORROW_IO_API_KEY
METEOBLUE_API_KEY
METEO_AZ_VALUE_HEADER
CALLMEBOT_PHONE
CALLMEBOT_APIKEY
OPENAI_API_KEY
```

7. Deploy bitəndə server belə bir URL verəcək:

```text
https://xacmaz-weather-api.onrender.com
```

Əgər Render başqa URL verərsə, həmin URL-i istifadə et.

## Server işləyir yoxlaması

Browserdə aç:

```text
https://SERVER-URL/api/health
```

Cavabda `ok: true` görünməlidir.

## APK-ni cloud URL ilə yenidən yığmaq

`mobile_app` qovluğunda `.env` faylı yarat:

```text
EXPO_PUBLIC_API_BASE_URL=https://SERVER-URL
```

Sonra APK yığ:

```powershell
cd C:\Users\Admin\Desktop\xacmaz_weather\mobile_app
npm run build:apk
```

Bundan sonra APK kompüterə ehtiyac olmadan internet olan hər yerdə işləyəcək.
