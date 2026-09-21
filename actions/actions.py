import re
from datetime import datetime
from typing import Any, Text, Dict, List

from rasa_sdk import FormValidationAction, Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, ActiveLoop


# ============================================================
# HELPER FUNCTIONS
# ============================================================

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,

    # Hinglish
    "ek": 1,
    "do": 2,
    "teen": 3,
    "chaar": 4,
    "panch": 5,
    "che": 6,
    "saat": 7,
    "aat": 8,
    "nou": 9,
    "das": 10,
}


def normalize_number(value: Any):
    """
    Converts numeric text or number words into an integer.
    Returns None if conversion is not possible.
    """

    if value is None:
        return None

    text = str(value).lower().strip()

    if text in NUMBER_WORDS:
        return NUMBER_WORDS[text]

    match = re.search(r"\b\d+\b", text)

    if match:
        return int(match.group())

    for word, number in NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return number

    return None


def get_latest_entity(tracker: Tracker, entity_name: str):
    """
    Finds the latest occurrence of an entity in the latest user message.
    """

    entities = tracker.latest_message.get("entities", [])

    for entity in reversed(entities):
        if entity.get("entity") == entity_name:
            return entity.get("value")

    return None

def is_immediate_request(text: str) -> bool:
    text = text.lower().strip()

    # "not now" must NOT mean immediate
    if re.search(r"\bnot\s+now\b", text):
        return False

    return bool(
        re.search(r"\bright\s+now\b", text)
        or re.search(r"\bimmediately\b", text)
        or re.search(r"\bnow\b", text)
        or re.search(r"\babhi\b", text)
    )

# ============================================================
# PERSON 1 — ROOM BOOKING
# ============================================================

class ValidateBookingForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_booking_form"

    # --------------------------------------------------------
    # ROOM TYPE
    # --------------------------------------------------------

    def validate_room_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        valid_types = {
            "simple",
            "deluxe",
            "premium"
        }

        value = str(slot_value).lower().strip()

        # If the user accidentally provides the number first
        number = normalize_number(value)

        if number is not None and value not in valid_types:
            return {
                "room_type": None,
                "number_of_rooms": number
            }

        # Find valid room type
        detected_type = None

        for room_type in valid_types:
            if re.search(
                rf"\b{re.escape(room_type)}\b",
                value
            ):
                detected_type = room_type
                break

        if detected_type is None:
            dispatcher.utter_message(
                text="Please choose a valid room type: Simple, Deluxe, or Premium."
            )

            return {
                "room_type": None
            }

        return {
            "room_type": detected_type
        }

    # --------------------------------------------------------
    # NUMBER OF ROOMS
    # --------------------------------------------------------

    def validate_number_of_rooms(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        latest_text = str(
            tracker.latest_message.get("text", "")
        ).lower()

        # Reject explicit negative numbers
        if re.search(
            r"(?:^|\s)-\s*\d+\b|\bminus\s+\d+\b",
            latest_text
        ):
            dispatcher.utter_message(
                text="The number of rooms must be at least 1."
            )

            return {
                "number_of_rooms": None
            }

        number = normalize_number(slot_value)

        if number is None:
            dispatcher.utter_message(
                text="Please enter a valid number of rooms between 1 and 10."
            )

            return {
                "number_of_rooms": None
            }

        if number < 1:
            dispatcher.utter_message(
                text="The number of rooms must be at least 1."
            )

            return {
                "number_of_rooms": None
            }

        if number > 10:
            dispatcher.utter_message(
                text="You can book a maximum of 10 rooms at a time."
            )

            return {
                "number_of_rooms": None
            }

        return {
            "number_of_rooms": number
        }


# ============================================================
# RESET BOOKING
# ============================================================

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


# ============================================================
# CANCEL BOOKING
# ============================================================

class ActionCancelBooking(Action):

    def name(self) -> Text:
        return "action_cancel_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(
            text="Your room booking request has been cancelled."
        )

        return [
            SlotSet("room_type", None),
            SlotSet("number_of_rooms", None),
            ActiveLoop(None),
        ]

# ============================================================
# PERSON 2 — ROOM CLEANING
# ============================================================

RECURRENCE_MAP = {
    "every day": "daily",
    "everyday": "daily",
    "daily": "daily",
    "roz": "daily",
    "har roz": "daily",
    "har din": "daily",
    "har shaam": "daily",
    "every week": "weekly",
    "weekly": "weekly",
    "every month": "monthly",
    "monthly": "monthly",
    "twice a day": "twice daily",
    "once": "once",
    "one time": "once",
    "one-time": "once",
    "ek baar": "once",
}


class ValidateCleaningForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_cleaning_form"

    # --------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------

    @staticmethod
    def _extract_frequency(text: str):
        if not text:
            return None

        lower_text = text.lower()

        # Hinglish recurring time phrases
        if re.search(r"\bhar\s+(subah|morning|shaam|evening|raat|night)\b", lower_text):
            return "daily"

        for phrase in sorted(RECURRENCE_MAP.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(phrase)}\b", lower_text):
                return RECURRENCE_MAP[phrase]

        return None

    @staticmethod
    def _extract_time(text: str):
        if not text:
            return None

        lower_text = text.lower()

        date_prefix = ""
        date_match = re.search(r"\b(today|tomorrow|next\s+\w+)\b", lower_text)
        if date_match:
            date_prefix = date_match.group(0).capitalize() + " at "

        match = re.search(
            r"\b(1[0-2]|[1-9])"
            r"(?::[0-5][0-9])?"
            r"\s*(am|pm)\b",
            lower_text,
        )
        if match:
            time_str = match.group(0).upper()
            return (date_prefix + time_str) if date_prefix else time_str

        match = re.search(
            r"\b([01][0-9]|2[0-3]):[0-5][0-9]\b",
            text,
        )
        if match:
            time_str = match.group(0)
            return (date_prefix + time_str) if date_prefix else time_str

        periods = {
            "morning": "morning",
            "subah": "morning",
            "afternoon": "afternoon",
            "dopahar": "afternoon",
            "evening": "evening",
            "shaam": "evening",
            "night": "night",
            "raat": "night",
        }

        for word, norm in periods.items():
            if re.search(rf"\b{word}\b", lower_text):
                return (date_prefix + norm) if date_prefix else norm

        if date_prefix:
            return date_prefix.strip()

        return None

    # --------------------------------------------------------
    # CLEANING TYPE
    # --------------------------------------------------------

    def validate_cleaning_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        text = tracker.latest_message.get("text", "").lower()

        # Immediate
        if is_immediate_request(text):
            return {
                "cleaning_type": "immediate",
                "cleaning_time": "now",
                "cleaning_frequency": "once",
            }

        # Recurring
        freq = self._extract_frequency(text)
        if freq and freq != "once":
            return {
                "cleaning_type": "recurring",
                "cleaning_frequency": freq,
            }

        if any(word in text for word in ["every day", "daily", "every week", "weekly", "every month", "monthly", "roz", "har roz", "har din", "recurring"]):
            return {
                "cleaning_type": "recurring"
            }

        existing_type = tracker.get_slot("cleaning_type")
        existing_freq = tracker.get_slot("cleaning_frequency")

        # Preserve recurring if already set
        if existing_type == "recurring" or (existing_freq and existing_freq != "once"):
            return {
                "cleaning_type": "recurring",
                "cleaning_frequency": existing_freq or "daily"
            }

        # Scheduled
        time_found = self._extract_time(text)
        if time_found:
            return {
                "cleaning_type": "scheduled",
                "cleaning_time": time_found,
                "cleaning_frequency": existing_freq or "once",
            }

        if "scheduled" in text or "schedule" in text:
            return {
                "cleaning_type": "scheduled"
            }

        value = str(slot_value).lower().strip() if slot_value else ""
        if value in ["immediate", "immediately"]:
            return {
                "cleaning_type": "immediate",
                "cleaning_time": "now",
                "cleaning_frequency": "once",
            }
        if value in ["scheduled", "schedule"]:
            return {
                "cleaning_type": "scheduled"
            }
        if value in ["recurring"]:
            return {
                "cleaning_type": "recurring"
            }

        if existing_type:
            return {"cleaning_type": existing_type}

        dispatcher.utter_message(
            text="Please choose a cleaning type: immediate, scheduled, or recurring."
        )

        return {
            "cleaning_type": None
        }

    # --------------------------------------------------------
    # CLEANING TIME
    # --------------------------------------------------------

    def validate_cleaning_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        text = tracker.latest_message.get("text", "").lower()

        # Handle cancel keyword gracefully
        if any(w in text for w in ["cancel", "stop", "never mind", "forget it", "rehne do", "mat karo"]):
            return {}

        # 1. Immediate
        if is_immediate_request(text):
            return {
                "cleaning_time": "now"
            }

        time_found = self._extract_time(text)
        freq_found = self._extract_frequency(text)

        existing_time = tracker.get_slot("cleaning_time")
        existing_freq = tracker.get_slot("cleaning_frequency")
        existing_type = tracker.get_slot("cleaning_type")

        # 2. If valid time is in user's message
        if time_found:
            res = {"cleaning_time": time_found}
            if freq_found:
                res["cleaning_frequency"] = freq_found
                res["cleaning_type"] = "recurring"
            elif existing_freq and existing_freq != "once":
                res["cleaning_frequency"] = existing_freq
                res["cleaning_type"] = "recurring"
            elif existing_type == "recurring":
                res["cleaning_type"] = "recurring"
                res["cleaning_frequency"] = existing_freq or "daily"
            return res

        # 3. If user provided a frequency phrase ("every day", "every week", "daily", "weekly", "monthly", "roz", etc.)
        # but NO time in the current message
        if freq_found:
            res = {
                "cleaning_frequency": freq_found,
                "cleaning_type": "recurring",
            }
            if existing_time:
                res["cleaning_time"] = existing_time
            else:
                res["cleaning_time"] = None
            return res

        # 4. Check slot_value
        val_str = str(slot_value).lower().strip() if slot_value else ""
        time_from_val = self._extract_time(val_str)
        if time_from_val:
            res = {"cleaning_time": time_from_val}
            if existing_freq and existing_freq != "once":
                res["cleaning_frequency"] = existing_freq
                res["cleaning_type"] = "recurring"
            return res

        if val_str == "now":
            return {"cleaning_time": "now"}

        # 5. If tracker already has valid time
        if existing_time:
            res = {"cleaning_time": existing_time}
            if existing_freq and existing_freq != "once":
                res["cleaning_frequency"] = existing_freq
                res["cleaning_type"] = "recurring"
            return res

        # 6. Only utter error if the user provided something that is neither a time nor a recurrence phrase
        dispatcher.utter_message(
            text=(
                "Please specify a valid time, such as "
                "10 AM, 5 PM, morning, afternoon, evening, or night."
            )
        )

        return {
            "cleaning_time": None
        }


    # --------------------------------------------------------
    # CLEANING FREQUENCY
    # --------------------------------------------------------

    def validate_cleaning_frequency(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        text = tracker.latest_message.get("text", "").lower()

        freq_found = self._extract_frequency(text)
        if freq_found:
            res = {"cleaning_frequency": freq_found}
            if freq_found != "once":
                res["cleaning_type"] = "recurring"
            return res

        cleaning_type = tracker.get_slot("cleaning_type")

        if cleaning_type in ["immediate", "scheduled"]:
            return {
                "cleaning_frequency": "once"
            }

        val_str = str(slot_value).lower().strip() if slot_value else ""
        freq_from_val = self._extract_frequency(val_str)
        if freq_from_val:
            res = {"cleaning_frequency": freq_from_val}
            if freq_from_val != "once":
                res["cleaning_type"] = "recurring"
            return res

        existing_freq = tracker.get_slot("cleaning_frequency")
        if existing_freq:
            return {
                "cleaning_frequency": existing_freq
            }

        dispatcher.utter_message(
            text="Please specify a frequency such as once, daily, or weekly."
        )

        return {
            "cleaning_frequency": None
        }


# ============================================================
# DYNAMIC ASK FOR CLEANING TIME
# ============================================================

class ActionAskCleaningFormCleaningTime(Action):

    def name(self) -> Text:
        return "action_ask_cleaning_form_cleaning_time"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        freq = tracker.get_slot("cleaning_frequency")

        if freq == "daily":
            dispatcher.utter_message(
                text="What time would you like the daily room cleaning?"
            )
        elif freq == "weekly":
            dispatcher.utter_message(
                text="What time would you like the weekly room cleaning?"
            )
        elif freq == "monthly":
            dispatcher.utter_message(
                text="What time would you like the monthly room cleaning?"
            )
        elif freq and freq != "once":
            dispatcher.utter_message(
                text=f"What time would you like the {freq} room cleaning?"
            )
        else:
            dispatcher.utter_message(
                text=(
                    "What time would you like the cleaning? "
                    "You can say a specific time such as 5 PM, or morning, afternoon, evening, or night."
                )
            )

        return []


# ============================================================
# RESET CLEANING
# ============================================================

class ActionResetCleaning(Action):

    def name(self) -> Text:
        return "action_reset_cleaning"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        return [
            SlotSet("cleaning_type", None),
            SlotSet("cleaning_time", None),
            SlotSet("cleaning_frequency", None),
        ]


# ============================================================
# CANCEL CLEANING
# ============================================================

class ActionCancelCleaning(Action):

    def name(self) -> Text:
        return "action_cancel_cleaning"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(
            text="No problem! Your cleaning request has been cancelled."
        )

        return [
            SlotSet("cleaning_type", None),
            SlotSet("cleaning_time", None),
            SlotSet("cleaning_frequency", None),
            ActiveLoop(None),
        ]


class ActionCleaningConfirmation(Action):

    def name(self) -> Text:
        return "action_cleaning_confirmation"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        cleaning_type = tracker.get_slot("cleaning_type")
        cleaning_time = tracker.get_slot("cleaning_time")
        cleaning_frequency = tracker.get_slot("cleaning_frequency")

        if cleaning_type == "immediate":
            dispatcher.utter_message(
                text="Your immediate room cleaning request has been confirmed."
            )
        elif cleaning_type == "recurring":
            freq_str = cleaning_frequency or "daily"
            if cleaning_time:
                dispatcher.utter_message(
                    text=f"Your room cleaning has been scheduled {freq_str} at {cleaning_time}."
                )
            else:
                dispatcher.utter_message(
                    text=f"Your {freq_str} room cleaning has been scheduled."
                )
        elif cleaning_type == "scheduled":
            if cleaning_time:
                dispatcher.utter_message(
                    text=f"OK! Your room will be cleaned at {cleaning_time}."
                )
            else:
                dispatcher.utter_message(
                    text="Your room cleaning has been scheduled."
                )
        else:
            if cleaning_time:
                dispatcher.utter_message(
                    text=f"OK! Your room will be cleaned at {cleaning_time}."
                )
            else:
                dispatcher.utter_message(
                    text="Your room cleaning request has been confirmed."
                )

        return [
            SlotSet("cleaning_type", None),
            SlotSet("cleaning_time", None),
            SlotSet("cleaning_frequency", None),
        ]


# ============================================================
# TIME-BASED GREETING
# ============================================================

class ActionTimeBasedGreeting(Action):

    def name(self) -> Text:
        return "action_time_based_greeting"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        hour = datetime.now().hour

        if 5 <= hour < 12:
            greeting = (
                "Good morning! Welcome to our hotel. "
                "How may I assist you today?"
            )
        elif 12 <= hour < 17:
            greeting = (
                "Good afternoon! Welcome to our hotel. "
                "How may I assist you today?"
            )
        elif 17 <= hour < 22:
            greeting = (
                "Good evening! Welcome to our hotel. "
                "How may I assist you today?"
            )
        else:
            greeting = (
                "Good evening! Welcome to our hotel. "
                "How may I assist you tonight?"
            )

        dispatcher.utter_message(
            text=greeting
        )

        return []


class ActionStartCleaning(Action):

    def name(self) -> Text:
        return "action_start_cleaning"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        text = tracker.latest_message.get("text", "").lower()

        existing_type = tracker.get_slot("cleaning_type")
        existing_time = tracker.get_slot("cleaning_time")
        existing_freq = tracker.get_slot("cleaning_frequency")

        extracted_freq = ValidateCleaningForm._extract_frequency(text)
        extracted_time = ValidateCleaningForm._extract_time(text)

        # Immediate
        if is_immediate_request(text):
            return [
                SlotSet("cleaning_type", "immediate"),
                SlotSet("cleaning_time", "now"),
                SlotSet("cleaning_frequency", "once"),
            ]

        cleaning_freq = extracted_freq or existing_freq
        cleaning_time = extracted_time or existing_time

        if cleaning_freq in ["daily", "weekly", "monthly", "twice daily"] or "recurring" in text:
            cleaning_type = "recurring"
        elif cleaning_time or "scheduled" in text or "schedule" in text:
            cleaning_type = "scheduled"
            if not cleaning_freq:
                cleaning_freq = "once"
        else:
            cleaning_type = "scheduled"
            if not cleaning_freq:
                cleaning_freq = "once"

        return [
            SlotSet("cleaning_type", cleaning_type),
            SlotSet("cleaning_time", cleaning_time),
            SlotSet("cleaning_frequency", cleaning_freq),
        ]
