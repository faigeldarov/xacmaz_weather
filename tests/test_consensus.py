import unittest
from datetime import timedelta

from consensus import find_spray_windows, local_now, merge_hourly_data, normalize_datetime
from fetchers import _meteo_az_item_to_hourly, parse_gismeteo_html


class ConsensusTests(unittest.TestCase):
    def test_timezone_offset_is_normalized_to_baku_time(self):
        dt = normalize_datetime("2099-01-01T00:00:00+00:00")
        self.assertEqual(dt.strftime("%Y-%m-%d %H:%M"), "2099-01-01 04:00")

    def test_precipitation_uses_source_weights(self):
        sources = {
            "strong": [{
                "datetime": "2099-06-08 06:00",
                "wind_kmh": 10,
                "precip_prob": 100,
                "temperature": 20,
            }],
            "weak": [{
                "datetime": "2099-06-08 06:00",
                "wind_kmh": 10,
                "precip_prob": 0,
                "temperature": 20,
            }],
        }

        merged = merge_hourly_data(sources, {"strong": 3, "weak": 1})
        self.assertEqual(merged["2099-06-08 06:00"]["precip_prob"], 75.0)

    def test_missing_hour_splits_spray_windows(self):
        start = (local_now() + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        first_hour = start.strftime("%Y-%m-%d %H:00")
        second_hour = (start + timedelta(hours=2)).strftime("%Y-%m-%d %H:00")

        merged = {
            first_hour: {
                "wind_kmh": 5,
                "precip_prob": 0,
                "source_count": 3,
                "wind_uncertainty": 0,
                "precip_uncertainty": 0,
            },
            second_hour: {
                "wind_kmh": 5,
                "precip_prob": 0,
                "source_count": 3,
                "wind_uncertainty": 0,
                "precip_uncertainty": 0,
            },
        }

        windows = find_spray_windows(merged)
        self.assertEqual(len(windows), 2)
        self.assertEqual(len(windows[0]), 1)
        self.assertEqual(len(windows[1]), 1)

    def test_meteo_az_daily_item_becomes_preferred_hour_records(self):
        records = _meteo_az_item_to_hourly("Xaçmaz", "7 günlük", {
            "start_at": "2099-06-08T00:00:00",
            "temp": 24,
            "wind_speed": 5,
            "precip_prob": 20,
            "humidity": 60,
            "wind_dir": 90,
        })

        self.assertEqual(len(records), 15)
        self.assertEqual(records[0]["datetime"], "2099-06-08 06:00")
        self.assertEqual(records[-1]["datetime"], "2099-06-08 20:00")
        self.assertEqual(records[0]["wind_kmh"], 18.0)
        self.assertEqual(records[0]["wind_direction"], "Şərq")

    def test_gismeteo_html_becomes_program_records(self):
        html = """
        <div class="widget-row widget-row-tod-date">
          <div class="row-item">пн, 8 июня</div>
        </div>
        <div class="widget-row widget-row-datetime-time">
          <div class="row-item">Ночь</div>
          <div class="row-item">Утро</div>
          <div class="row-item">День</div>
          <div class="row-item">Вечер</div>
        </div>
        <div class="widget-row widget-row-icon">
          <div class="row-item"><span data-tooltip="Ясно"></span></div>
          <div class="row-item"><span data-tooltip="Облачно"></span></div>
          <div class="row-item"><span data-tooltip="Дождь"></span></div>
          <div class="row-item"><span data-tooltip="Пасмурно"></span></div>
        </div>
        <div class="widget-row widget-row-chart-temperature-air">
          <temperature-value value="16"></temperature-value>
          <temperature-value value="21"></temperature-value>
          <temperature-value value="27"></temperature-value>
          <temperature-value value="22"></temperature-value>
        </div>
        <div class="widget-row widget-row-wind">
          <div class="row-item"><div class="wind-speed"><speed-value value="2"></speed-value></div><div class="wind-gust"><speed-value value="4"></speed-value></div></div>
          <div class="row-item"><div class="wind-speed"><speed-value value="3"></speed-value></div><div class="wind-gust"><speed-value value="5"></speed-value></div></div>
          <div class="row-item"><div class="wind-speed"><speed-value value="4"></speed-value></div><div class="wind-gust"><speed-value value="6"></speed-value></div></div>
          <div class="row-item"><div class="wind-speed"><speed-value value="5"></speed-value></div><div class="wind-gust"><speed-value value="7"></speed-value></div></div>
        </div>
        <div class="widget-row widget-row-precipitation-bars">
          <div class="row-item">0</div>
          <div class="row-item">0,1</div>
          <div class="row-item">1</div>
          <div class="row-item">3</div>
        </div>
        <div class="widget-row widget-row-humidity">
          <div class="row-item">80</div>
          <div class="row-item">70</div>
          <div class="row-item">60</div>
          <div class="row-item">65</div>
        </div>
        """

        records = parse_gismeteo_html(html)
        expected_year = local_now().year
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]["datetime"], f"{expected_year}-06-08 00:00")
        self.assertEqual(records[2]["datetime"], f"{expected_year}-06-08 12:00")
        self.assertEqual(records[2]["temperature"], 27.0)
        self.assertEqual(records[2]["wind_kmh"], 14.4)
        self.assertEqual(records[1]["precip_prob"], 30)
        self.assertEqual(records[2]["precip_prob"], 60)
        self.assertEqual(records[3]["precip_prob"], 85)

    def test_gismeteo_tomorrow_time_slots_are_parsed(self):
        html = """
        <div class="widget-row widget-row-datetime-date">
          <div class="row-item">вт, 9 июня завтра</div>
        </div>
        <div class="widget-row widget-row-datetime-time">
          <div class="row-item">1:00</div>
          <div class="row-item">4:00</div>
          <div class="row-item">7:00</div>
        </div>
        <div class="widget-row widget-row-chart-temperature-air">
          <temperature-value value="16"></temperature-value>
          <temperature-value value="17"></temperature-value>
          <temperature-value value="20"></temperature-value>
        </div>
        <div class="widget-row widget-row-wind">
          <div class="row-item"><div class="wind-speed"><speed-value value="2"></speed-value></div><div class="wind-gust"><speed-value value="4"></speed-value></div></div>
          <div class="row-item"><div class="wind-speed"><speed-value value="3"></speed-value></div><div class="wind-gust"><speed-value value="5"></speed-value></div></div>
          <div class="row-item"><div class="wind-speed"><speed-value value="4"></speed-value></div><div class="wind-gust"><speed-value value="6"></speed-value></div></div>
        </div>
        <div class="widget-row widget-row-precipitation-bars">
          <div class="row-item">0</div>
          <div class="row-item">0</div>
          <div class="row-item">0,1</div>
        </div>
        <div class="widget-row widget-row-humidity">
          <div class="row-item">87</div>
          <div class="row-item">88</div>
          <div class="row-item">84</div>
        </div>
        """

        records = parse_gismeteo_html(html)
        expected_year = local_now().year
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["datetime"], f"{expected_year}-06-09 01:00")
        self.assertEqual(records[1]["datetime"], f"{expected_year}-06-09 04:00")
        self.assertEqual(records[2]["datetime"], f"{expected_year}-06-09 07:00")
        self.assertEqual(records[2]["precip_prob"], 30)


if __name__ == "__main__":
    unittest.main()
