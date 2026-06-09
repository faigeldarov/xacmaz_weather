# Xaçmaz Çiləmə Mobile

Expo/React Native mobil app. Backend `C:\Users\Admin\Desktop\xacmaz_weather` içindəki FastAPI serveridir.

## Backend

```powershell
cd C:\Users\Admin\Desktop\xacmaz_weather
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

## Mobile app

```powershell
cd C:\Users\Admin\Desktop\xacmaz_weather\mobile_app
npm install
npx expo start
```

Telefonla test edəndə API URL sahəsində kompüterin lokal IP ünvanını yaz:

```text
http://192.168.1.25:8000
```

Windows-da IP-ni görmək üçün:

```powershell
ipconfig
```
