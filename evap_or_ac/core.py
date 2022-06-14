""" Core of Evap_or_AC """
import asyncio
import os
from typing import Dict, List, Optional

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
        self.aqi = self.get_aqi(zipcode, airnow_key)
        self.answer = self.get_answer(self.aqi, aqi_threshold)

    def get_answer(self, aqi: List[Dict], aqi_threshold: int) -> Dict:
        """
        Provide answer to question: Would it be better to use an
        evaporative cooler or air conditioning?
        """

        # check whether there are AQI greater than the provided threshold.
        # if there are any above this level, we return air conditioning.
        if len([x for x in aqi if x["AQI"] > aqi_threshold]) > 0:
            return {
                "answer": "Air Conditioning",
                "why": f"An AQI greater than threshold {aqi_threshold} was found.",
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
