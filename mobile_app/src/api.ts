import { AdviceResponse, SendWhatsAppResponse } from "./types";

const DEFAULT_CLOUD_API_BASE_URL = "https://xacmaz-weather-api.onrender.com";

export const DEFAULT_API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL?.trim() || DEFAULT_CLOUD_API_BASE_URL;

function cleanBaseUrl(apiBaseUrl: string) {
  return apiBaseUrl.trim().replace(/\/+$/, "");
}

async function requestJson<T>(url: string, options: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });
  } catch (error) {
    throw new Error(
      error instanceof Error
        ? `Serverə qoşulmaq alınmadı: ${error.message}`
        : "Serverə qoşulmaq alınmadı."
    );
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = data?.detail || data?.error || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data as T;
}

export function fetchAdvice(apiBaseUrl: string, activeSubstance: string, crop: string) {
  return requestJson<AdviceResponse>(`${cleanBaseUrl(apiBaseUrl)}/api/advice`, {
    method: "POST",
    body: JSON.stringify({
      active_substance: activeSubstance,
      crop
    })
  });
}

export function sendWhatsApp(apiBaseUrl: string, message: string, phone: string) {
  return requestJson<SendWhatsAppResponse>(`${cleanBaseUrl(apiBaseUrl)}/api/send-whatsapp`, {
    method: "POST",
    body: JSON.stringify({
      message,
      phone
    })
  });
}
