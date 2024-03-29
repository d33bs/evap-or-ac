""" Core of Evap_or_AC """
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional

import psychrolib
import requests
from noaa_sdk import NOAA
from pyairnow import WebServiceAPI as airnow

# set International System (SI) for psychrolib
psychrolib.SetUnitSystem(psychrolib.SI)


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
        self.noaa_avg_temperature = self.get_noaa_today_avg_value(
            item_name="temperature"
        )
        self.avg_wet_bulb_temperature = self.get_avg_wet_bulb_temperature()
        self.avg_evap_temp_achievable = self.get_avg_evap_temp_achievable()
        self.answer = self.get_answer()

    @staticmethod
    def to_fahrenheit(celsius):
        """
        Convert celsius to fahrenheit
        """

        return celsius * 9 / 5 + 32

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
        # or equal to 115, a temperature which will mean it's unlikely evap
        # cooling will be effective.
        if (
            len(
                [
                    x
                    for x in self.noaa_weather["temperature"]["values"]
                    if self.to_fahrenheit(x["value"]) >= 115
                ]
            )
            > 0
        ):
            return {
                "answer": "Air Conditioning",
                "why": f"A daily temperature above 115 F was discovered in the weather forecast",
            }

        # check whether the possible evaporative cooling temperature achievable
        # will be above 75 degrees.
        if self.to_fahrenheit(self.avg_evap_temp_achievable) > 75:
            return {
                "answer": "Air Conditioning",
                "why": f"The average achievable evaporative cooler temperature is above 75 F.",
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

        # referential lat and lon via aqi lookup
        lat = self.aqi[0]["Latitude"]
        lon = self.aqi[0]["Longitude"]

        return float(
            requests.get(
                f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
            ).json()["results"][0]["elevation"]
        )

    def get_atmospheric_pressure(self) -> dict:
        """
        Determine atmospheric pressure using barometric formula.

        https://en.wikipedia.org/wiki/Atmospheric_pressure
        """

        # in hPa
        p = 101325 * pow(
            (1 - ((0.00976 * self.altitude) / 288.16)),
            ((9.80665 * 0.02896968)) / (8.314462618 * 0.00976),
        )

        # hPa to Pa conversion
        return p * 100

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
            x["value"]
            for x in self.noaa_weather[item_name]["values"]
            if today in x["validTime"]
        ]
        return sum(vals) / len(vals)

    def get_avg_evap_temp_achievable(self) -> float:
        """
        Determine average evaporative cooling temperature achievable given weather data.

        Use the following algorithm:
            SAT = (TDB) - (e * (TDB - TWB))

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

        # note: we assume a 90% efficiency for the evaporative cooling unit
        return (self.noaa_avg_temperature) - (
            0.9 * (self.noaa_avg_temperature - self.avg_wet_bulb_temperature)
        )

    def get_avg_wet_bulb_temperature(self) -> float:
        """
        Gets the wet bulb temperature based on weather data.
        """

        return psychrolib.GetTWetBulbFromRelHum(
            TDryBulb=self.noaa_avg_temperature,
            RelHum=self.noaa_avg_relhumidity / 100,
            Pressure=self.atmospheric_pressure,
        )
