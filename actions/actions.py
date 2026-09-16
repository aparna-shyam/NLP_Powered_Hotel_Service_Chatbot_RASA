from typing import Any, Text, Dict, List
from datetime import datetime

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop, AllSlotsReset
from rasa_sdk.types import DomainDict


# ---------------------------------------------------------------------------
# Form Validation: Room Cleaning Form
# ---------------------------------------------------------------------------

class ValidateRoomCleaningForm(FormValidationAction):
    """Validates slots collected by the room_cleaning_form."""

    def name(self) -> Text:
        return "validate_room_cleaning_form"

    def validate_room_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate that the room number is a valid number (100-999)."""
        # Extract digits only
        room = str(slot_value).strip()
        digits = "".join(filter(str.isdigit, room))

        if digits and 100 <= int(digits) <= 999:
            return {"room_number": digits}
        else:
            dispatcher.utter_message(
                text=(
                    "I'm sorry, that doesn't look like a valid room number. "
                    "Our rooms are numbered between 100 and 999. "
                    "Could you please provide your room number again?"
                )
            )
            return {"room_number": None}

    def validate_cleaning_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate that the cleaning time is not empty and is reasonable."""
        time_value = str(slot_value).strip().lower()

        valid_keywords = [
            "am", "pm", "morning", "afternoon", "evening", "noon",
            "midnight", ":", "0", "1", "2", "3", "4", "5", "6",
            "7", "8", "9"
        ]

        if time_value and any(kw in time_value for kw in valid_keywords):
            return {"cleaning_time": slot_value}
        else:
            dispatcher.utter_message(
                text=(
                    "Please provide a valid time for the cleaning, "
                    "for example: '10:00 AM', '2 PM', or 'morning'."
                )
            )
            return {"cleaning_time": None}

    def validate_cleaning_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate that cleaning type is one of the accepted options."""
        value = str(slot_value).strip().lower()

        mapping = {
            "full cleaning": "full cleaning",
            "full clean": "full cleaning",
            "deep clean": "full cleaning",
            "complete": "full cleaning",
            "option 1": "full cleaning",
            "1": "full cleaning",
            "quick tidy": "quick tidy",
            "quick": "quick tidy",
            "tidy": "quick tidy",
            "option 2": "quick tidy",
            "2": "quick tidy",
            "fresh towels only": "fresh towels only",
            "fresh towels": "fresh towels only",
            "just towels": "fresh towels only",
            "towels": "fresh towels only",
            "towels only": "fresh towels only",
            "option 3": "fresh towels only",
            "3": "fresh towels only",
            "turn down service": "turn down service",
            "turn down": "turn down service",
            "turndown": "turn down service",
            "option 4": "turn down service",
            "4": "turn down service",
        }

        cleaned = mapping.get(value)
        if cleaned:
            return {"cleaning_type": cleaned}
        else:
            dispatcher.utter_message(
                text=(
                    "Please choose one of the cleaning types:\n"
                    "1. Full cleaning\n"
                    "2. Quick tidy\n"
                    "3. Fresh towels only\n"
                    "4. Turn down service"
                )
            )
            return {"cleaning_type": None}


# ---------------------------------------------------------------------------
# Custom Action: Submit Room Cleaning Request
# ---------------------------------------------------------------------------

class ActionSubmitRoomCleaning(Action):
    """Confirms the room cleaning request after form is completed."""

    def name(self) -> Text:
        return "action_submit_room_cleaning"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:

        room_number = tracker.get_slot("room_number")
        cleaning_time = tracker.get_slot("cleaning_time")
        cleaning_type = tracker.get_slot("cleaning_type")

        # Log the request with a timestamp (simulating backend submission)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        dispatcher.utter_message(
            text=(
                f"Your room cleaning request has been confirmed!\n\n"
                f"- Room: {room_number}\n"
                f"- Cleaning type: {cleaning_type.title()}\n"
                f"- Scheduled time: {cleaning_time}\n\n"
                f"Our housekeeping team will arrive at your room at the requested time. "
                f"If you need to make any changes, please call the front desk at extension 0."
            )
        )

        # Reset slots after submission so next request starts fresh
        return [
            SlotSet("room_number", None),
            SlotSet("cleaning_time", None),
            SlotSet("cleaning_type", None),
        ]


# ---------------------------------------------------------------------------
# Custom Action: Cancel Room Cleaning Request
# ---------------------------------------------------------------------------

class ActionCancelRoomCleaning(Action):
    """Cancels an in-progress or pending room cleaning request."""

    def name(self) -> Text:
        return "action_cancel_room_cleaning"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(
            text=(
                "Your room cleaning request has been cancelled. "
                "No housekeeping will be sent. "
                "If you change your mind, feel free to ask again!"
            )
        )

        return [
            SlotSet("room_number", None),
            SlotSet("cleaning_time", None),
            SlotSet("cleaning_type", None),
            ActiveLoop(None),
        ]
