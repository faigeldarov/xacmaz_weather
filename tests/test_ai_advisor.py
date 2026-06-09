import unittest
from datetime import timedelta

from ai_advisor import build_ai_payload
from consensus import local_now


class AiAdvisorPayloadTests(unittest.TestCase):
    def test_ai_payload_keeps_only_three_hour_windows_in_next_three_days(self):
        start = (local_now() + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
        short_start = start.replace(hour=18)

        def iso(dt):
            return dt.isoformat(timespec="minutes")

        hourly = []
        for i in range(3):
            dt = start + timedelta(hours=i)
            hourly.append({
                "datetime": dt.strftime("%Y-%m-%d %H:00"),
                "wind_kmh": 10,
                "precip_prob": 5,
                "temperature": 22 + i,
                "humidity": 65,
                "source_count": 6,
            })

        forecast_payload = {
            "generated_at": local_now().isoformat(timespec="seconds"),
            "successful_sources": ["open_meteo", "meteo_az"],
            "failed_sources": [],
            "hourly": hourly,
            "windows": [
                {
                    "index": 1,
                    "start": iso(start),
                    "end": iso(start + timedelta(hours=3)),
                    "duration_hours": 3,
                    "avg_wind_kmh": 10,
                    "avg_precip_prob": 5,
                    "avg_source_count": 6,
                    "confidence": "high",
                    "hours": [
                        {
                            "wind_uncertainty": 1,
                            "precip_uncertainty": 2,
                        }
                    ],
                },
                {
                    "index": 2,
                    "start": iso(short_start),
                    "end": iso(short_start + timedelta(hours=1)),
                    "duration_hours": 1,
                    "avg_wind_kmh": 9,
                    "avg_precip_prob": 0,
                    "avg_source_count": 6,
                    "confidence": "high",
                    "hours": [],
                },
            ],
        }

        payload = build_ai_payload("captan", "şaftalı/gilas", forecast_payload=forecast_payload)
        self.assertEqual(len(payload["candidate_windows"]), 1)
        self.assertEqual(payload["candidate_windows"][0]["duration_hours"], 3)
        self.assertEqual(payload["candidate_windows"][0]["avg_temperature_c"], 23)
        self.assertEqual(payload["rejected_summary"]["too_short_windows"], 1)


if __name__ == "__main__":
    unittest.main()
