""" Core of Evap_or_AC """
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional

from noaa_sdk import NOAA
import psychrolib
from pyairnow import WebServiceAPI as airnow


class EvapOrAC:
    """
    Class for gathering, assessing, and returning information concerning
    evaporative cooling or air conditioning based on weather and air quality data.
    """

    def __init__(
        self, zipcode: str, airnow_key: Optional[str] = None, aqi_threshold: int = 101
    ) -> None:
        zipcode = os.environ.get("ZIPCODE", zipcode)
        airnow_key = os.environ.get("AIRNOW_KEY", airnow_key)
        self.aqi_threshold = aqi_threshold
        self.aqi = self.get_aqi(zipcode, airnow_key)
        self.altitude = self.get_altitude()
        self.atmospheric_pressure = self.get_atmospheric_pressure()
        self.noaa_weather = self.get_noaa_weather(zipcode)
        self.noaa_avg_relhumidity = self.get_noaa_today_avg_value(
            item_name="relativeHumidity"
        )
        self.avg_wet_bulb_temperature = self.get_avg_wet_bulb_temperature()
        self.noaa_avg_temperature = self.get_noaa_today_avg_value(
            item_name="temperature"
        )
        self.answer = self.get_answer()

    def get_answer(self) -> Dict:
        """
        Provide answer to question: Would it be better to use an
        evaporative cooler or air conditioning?
        """

        # check whether there are AQI greater than the provided threshold.
        # if there are any above this level, we return air conditioning.
        if len([x for x in self.aqi if x["AQI"] > self.aqi_threshold]) > 0:
            return {
                "answer": "Air Conditioning",
                "why": f"An AQI greater than threshold {self.aqi_threshold} was found.",
            }

        # check weather we have a temperature sometime today which is above
        # or equal to 105, a temperature which will mean it's unlikely evap
        # cooling will be effective
        if len([x for x in self.noaa_weather if x["temperature"] >= 105]) > 0:
            return {
                "answer": "Air Conditioning",
                "why": f"A daily temperature above 105 F was discovered in the weather forecast",
            }

        return {
            "answer": "Evaporative Cooler",
            "why": "Good day for evaporative cooling.",
        }

    def get_aqi(self, zipcode: str, airnow_key: Optional[str]) -> List[Dict]:
        """
        Get AQI from AirNow using key and zipcode
        """

        return asyncio.run(
            airnow(airnow_key).forecast.zipCode(
                zipcode,
                distance=30,
            )
        )

    def get_altitude(self) -> float:
        """
        Get the altitude based on the relative latitude and longitude returned
        from AQI request. Utilizes Open Elevation API.

        https://github.com/Jorl17/open-elevation/blob/master/docs/api.md
        """
        lat = self.aqi[0]["Latitude"]
        lon = self.aqi[0]["Longitude"]

        return float(
            requests.get(
                "https://api.open-elevation.com/api/v1/lookup?locations={latitude},{longitude}"
            ).json()["results"][0]["elevation"]
        )

    def get_atmospheric_pressure(self) -> dict:
        """
        Determine atmospheric pressure using barometric formula.

        https://en.wikipedia.org/wiki/Atmospheric_pressure
        """

        # in hPa
        p = 101325 * (
            1 - ((0.00976 * self.altitude) / 288.16)
            ^ ((9.80665 * 0.02896968)) / (8.314462618 * 0.00976)
        )

        # to psi
        psi = p * 0.014503773800722

        return psi

    def get_noaa_weather(self, zipcode: str) -> List[Dict]:
        """
        Get NOAA weather data using zipcode
        """

        return NOAA().get_forecasts(
            postal_code=zipcode, country="US", type="forecastGridData"
        )

    def get_noaa_today_avg_value(self, item_name: str) -> float:
        """
        Gets today's average relative humidity from NOAA weather data
        """

        today = datetime.today().strftime("%Y-%m-%d")
        vals = [
            x["value"] for x in result[item_name]["values"] if today in x["validTime"]
        ]
        return sum(vals) / len(vals)

    def get_avg_temp_drop_achievable(self) -> float:
        """
        Determine avg temp drop achievable given weather data.

        Use the following algorithm:
            SAT = e * (TDB - TWB) - (TDB)

        Based on:
            e = (TDB - SAT) / (TDB - TWB)

        Where:
            e = the cooling effectiveness of the cooler
            TDB = the outdoor dry-bulb temperature
            TWB = the outdoor wet-bulb temperature
            SAT = the supply air temperature leaving the evaporative cooler
            Note. TDB - TWB = the wet-bulb depression

        Source: https://basc.pnnl.gov/resource-guides/evaporative-cooling-systems#edit-group-description
        """

        return

    def get_avg_wet_bulb_temperature(self) -> float:
        """
        Gets the wet bulb temperature based on weather data.
        """

        return psychrolib.GetTWetBulbFromRelHum(
            TDryBulb=self.noaa_avg_temperature,
            RelHum=self.noaa_avg_relhumidity,
            Pressure=self.atmospheric_pressure,
        )
