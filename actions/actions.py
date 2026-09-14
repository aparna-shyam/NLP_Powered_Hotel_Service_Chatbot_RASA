from typing import Any, Text, Dict, List

from rasa_sdk import FormValidationAction, Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet


class ValidateBookingForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_booking_form"

    def validate_room_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        valid_types = ["simple", "deluxe", "premium"]

        if slot_value.lower() not in valid_types:
            dispatcher.utter_message(
                text="Please choose Simple, Deluxe, or Premium."
            )
            return {"room_type": None}

        return {"room_type": slot_value.lower()}

    def validate_number_of_rooms(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        try:
            number = int(slot_value)
        except (ValueError, TypeError):
            dispatcher.utter_message(
                text="Please enter a valid number of rooms between 1 and 10."
            )
            return {"number_of_rooms": None}

        if number < 1 or number > 10:
            dispatcher.utter_message(
                text="Please enter a number of rooms between 1 and 10."
            )
            return {"number_of_rooms": None}

        return {"number_of_rooms": number}


class ActionResetBooking(Action):

    def name(self) -> Text:
        return "action_reset_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        return [
            SlotSet("room_type", None),
            SlotSet("number_of_rooms", None),
        ]