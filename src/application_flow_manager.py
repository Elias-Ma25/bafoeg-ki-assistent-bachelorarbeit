from __future__ import annotations

from datetime import date, datetime
from typing import Any


class ApplicationFlowManager:
    """Steuert einen dokumentenbasierten, adaptiven BAföG-Erstantrag.

    Die Fragen sind kein starrer Katalog. Ein Schritt wird nur gestellt,
    wenn die zugehörige Information weder aus einem Dokument übernommen
    noch bereits vom Nutzer bestätigt wurde.
    """

    ASSET_LIMIT_UNDER_30 = 10_000
    ASSET_LIMIT_FROM_30 = 30_000

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = [
            {
                "key": "geburtsdatum",
                "target": "user_profile",
                "target_fields": ["geburtsdatum"],
                "question": "Wie lautet dein Geburtsdatum? Bitte im Format TT.MM.JJJJ.",
                "help": (
                    "Das Geburtsdatum wird für Formblatt 1 und für die altersabhängige "
                    "Vermögensfrage benötigt."
                ),
            },
            {
                "key": "vollzeitausbildung",
                "target": "case_state",
                "target_fields": ["vollzeitausbildung"],
                "question": "Handelt es sich bei deinem Studium um ein Vollzeitstudium?",
                "help": (
                    "Ein reguläres Studium mit der vorgesehenen vollen Studienbelastung "
                    "ist gewöhnlich ein Vollzeitstudium. Bei Teilzeit- oder berufsbegleitenden "
                    "Modellen wähle nicht vorschnell „Ja“."
                ),
            },
            {
                "key": "wohnsituation_und_eigentum",
                "target": "case_state",
                "target_fields": ["wohnsituation", "wohnraum_eigentum_eltern"],
                "question": (
                    "Wohnst du während der Ausbildung mit deinen Eltern oder einem Elternteil zusammen? "
                    "Falls nein: Gehört der Wohnraum deinen Eltern oder einem Elternteil?"
                ),
                "help": (
                    "Gemeint ist die tatsächliche Wohnsituation während der Ausbildung. "
                    "Bei einer WG, einem Wohnheim oder einer eigenen Mietwohnung wohnst du "
                    "grundsätzlich nicht mit deinen Eltern zusammen."
                ),
            },
            {
                "key": "familienstand",
                "target": "case_state",
                "target_fields": ["familienstand"],
                "question": "Was ist dein Familienstand?",
                "help": (
                    "Wähle ledig, verheiratet bzw. eingetragene Lebenspartnerschaft, "
                    "dauernd getrennt lebend, verwitwet oder geschieden."
                ),
            },
            {
                "key": "kinder",
                "target": "case_state",
                "target_fields": ["kinder"],
                "question": "Hast du eigene Kinder?",
                "help": "Bei eigenen Kindern kann zusätzlich Formblatt 4 erforderlich sein.",
            },
            {
                "key": "kranken_pflegeversicherung",
                "target": "case_state",
                "target_fields": [
                    "krankenversicherung",
                    "pflegeversicherung_selbst_beitragspflichtig",
                ],
                "question": (
                    "Wie bist du während der Ausbildung kranken- und pflegeversichert?"
                ),
                "help": (
                    "Typische Möglichkeiten sind gesetzliche Familienversicherung, "
                    "studentische gesetzliche Versicherung, freiwillige gesetzliche "
                    "Versicherung, private Versicherung oder eine andere Versicherungsform."
                ),
            },
            {
                "key": "eigenes_einkommen",
                "target": "case_state",
                "target_fields": ["eigenes_einkommen"],
                "question": (
                    "Wirst du im beantragten Bewilligungszeitraum eigenes Einkommen haben, "
                    "zum Beispiel aus einem Minijob, Werkstudentenjob, Praktikum oder einer Rente?"
                ),
                "help": "Bei eigenem Einkommen werden passende Einkommensnachweise angefordert.",
            },
            {
                "key": "vermoegen_unter_grenze",
                "target": "case_state",
                "target_fields": ["vermoegen_unter_grenze"],
                "question": "",
                "help": (
                    "Gemeint ist dein eigenes Vermögen, zum Beispiel Bargeld, Bankguthaben, "
                    "Wertpapiere, Kryptowährungen, Fahrzeuge oder Immobilien – nicht das Vermögen deiner Eltern."
                ),
            },
        ]

    @staticmethod
    def _value(container: dict, key: str) -> str:
        return str(container.get(key, {}).get("value", "")).strip()

    @staticmethod
    def parse_birthdate(value: str) -> date | None:
        value = str(value).strip()
        if not value:
            return None

        formats = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y")
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    def calculate_age(self, user_profile: dict, reference_date: date | None = None) -> int | None:
        birthdate = self.parse_birthdate(self._value(user_profile, "geburtsdatum"))
        if birthdate is None:
            return None

        today = reference_date or date.today()
        return today.year - birthdate.year - (
            (today.month, today.day) < (birthdate.month, birthdate.day)
        )

    def get_asset_limit(self, user_profile: dict, reference_date: date | None = None) -> int | None:
        age = self.calculate_age(user_profile, reference_date)
        if age is None:
            return None
        return self.ASSET_LIMIT_UNDER_30 if age < 30 else self.ASSET_LIMIT_FROM_30

    def build_asset_question(self, user_profile: dict) -> str:
        age = self.calculate_age(user_profile)
        limit = self.get_asset_limit(user_profile)

        if age is None or limit is None:
            return (
                "Liegt dein eigenes Vermögen unter dem für dein Alter geltenden Freibetrag? "
                "Falls dein Geburtsdatum noch fehlt, ergänze es bitte zuerst."
            )

        formatted_limit = f"{limit:,.0f}".replace(",", ".")
        return (
            f"Du bist nach dem gespeicherten Geburtsdatum {age} Jahre alt. "
            f"Liegt dein eigenes Vermögen insgesamt unter {formatted_limit} Euro?\n\n"
            "Zum Vermögen zählen zum Beispiel Bargeld, Giro- und Sparkonten, Wertpapiere, "
            "Kryptowährungen, Fahrzeuge und Immobilien. Das Vermögen deiner Eltern ist nicht gemeint."
        )

    def build_question_text(
        self,
        step: dict,
        user_profile: dict,
        include_hint: bool = True,
    ) -> str:
        if step["key"] == "vermoegen_unter_grenze":
            question = self.build_asset_question(user_profile)
        else:
            question = step["question"]

        if include_hint:
            question += (
                "\n\nDu kannst eine Schnellauswahl anklicken, frei antworten "
                "oder direkt nachfragen, wenn etwas unklar ist."
            )
        return question

    def is_step_relevant(self, step: dict, user_profile: dict, case_state: dict) -> bool:
        return True

    def is_step_answered(self, step: dict, user_profile: dict, case_state: dict) -> bool:
        key = step["key"]

        if key == "geburtsdatum":
            return self.parse_birthdate(
                self._value(user_profile, "geburtsdatum")
            ) is not None

        if key == "wohnsituation_und_eigentum":
            wohnsituation = self._value(case_state, "wohnsituation").lower()
            eigentum = self._value(
                case_state,
                "wohnraum_eigentum_eltern",
            ).lower()

            if wohnsituation == "bei_eltern":
                return True
            if wohnsituation == "nicht_bei_eltern":
                return eigentum in {"ja", "nein"}
            return False

        if key == "kranken_pflegeversicherung":
            insurance = self._value(
                case_state,
                "krankenversicherung",
            ).lower()
            care = self._value(
                case_state,
                "pflegeversicherung_selbst_beitragspflichtig",
            ).lower()
            return (
                insurance
                in {
                    "familienversichert",
                    "studentisch_gesetzlich",
                    "freiwillig_gesetzlich",
                    "privat",
                    "anders",
                }
                and care in {"ja", "nein"}
            )

        target_container = (
            user_profile
            if step["target"] == "user_profile"
            else case_state
        )
        for field_name in step["target_fields"]:
            value = self._value(target_container, field_name).lower()
            if value and value != "unklar":
                return True
        return False

    def get_first_unanswered_step(self, user_profile: dict, case_state: dict) -> dict | None:
        for step in self.steps:
            if (
                self.is_step_relevant(step, user_profile, case_state)
                and not self.is_step_answered(step, user_profile, case_state)
            ):
                return step
        return None

    def get_step_by_key(self, step_key: str) -> dict | None:
        for step in self.steps:
            if step["key"] == step_key:
                return step
        return None

    def get_progress(self, user_profile: dict, case_state: dict) -> dict:
        relevant_steps = [
            step
            for step in self.steps
            if self.is_step_relevant(step, user_profile, case_state)
        ]
        answered = sum(
            1
            for step in relevant_steps
            if self.is_step_answered(step, user_profile, case_state)
        )
        total = len(relevant_steps)
        return {
            "total": total,
            "answered": answered,
            "open": total - answered,
            "percentage": round(answered / total * 100, 1) if total else 100.0,
        }
