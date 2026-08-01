from __future__ import annotations

from typing import Any


def _profile_value(user_profile: dict, key: str) -> str:
    return str(user_profile.get(key, {}).get("value", "")).strip()


def get_hybrid_options(
    step_key: str,
    user_profile: dict | None = None,
) -> list[dict[str, Any]]:
    """Liefert deterministische Schnellauswahlen für den aktuellen Antragsschritt.

    Jede Option enthält bereits die kanonischen internen Werte. Ein Klick wird
    deshalb ohne LLM interpretiert. Freitext bleibt parallel möglich.
    """
    user_profile = user_profile or {}

    options_by_step: dict[str, list[dict[str, Any]]] = {
        "vollzeitausbildung": [
            {
                "label": "Ja, Vollzeitstudium",
                "case_updates": {"vollzeitausbildung": "ja"},
            },
            {
                "label": "Nein, kein Vollzeitstudium",
                "case_updates": {"vollzeitausbildung": "nein"},
            },
        ],
        "wohnsituation_und_eigentum": [
            {
                "label": "Ich wohne bei meinen Eltern / einem Elternteil",
                "case_updates": {
                    "wohnsituation": "bei_eltern",
                    "wohnraum_eigentum_eltern": "nicht_relevant",
                },
            },
            {
                "label": "Nicht bei Eltern; Wohnraum gehört nicht meinen Eltern",
                "case_updates": {
                    "wohnsituation": "nicht_bei_eltern",
                    "wohnraum_eigentum_eltern": "nein",
                },
            },
            {
                "label": "Nicht bei Eltern; Wohnraum gehört meinen Eltern",
                "case_updates": {
                    "wohnsituation": "nicht_bei_eltern",
                    "wohnraum_eigentum_eltern": "ja",
                },
            },
        ],
        "familienstand": [
            {
                "label": "Ledig",
                "case_updates": {"familienstand": "ledig"},
            },
            {
                "label": "Verheiratet / eingetragene Lebenspartnerschaft",
                "case_updates": {"familienstand": "verheiratet"},
            },
            {
                "label": "Dauernd getrennt lebend",
                "case_updates": {"familienstand": "dauernd_getrennt"},
            },
            {
                "label": "Verwitwet",
                "case_updates": {"familienstand": "verwitwet"},
            },
            {
                "label": "Geschieden / Lebenspartnerschaft aufgehoben",
                "case_updates": {"familienstand": "geschieden"},
            },
        ],
        "kinder": [
            {
                "label": "Ja, ich habe eigene Kinder",
                "case_updates": {"kinder": "ja"},
            },
            {
                "label": "Nein, keine eigenen Kinder",
                "case_updates": {"kinder": "nein"},
            },
        ],
        "kranken_pflegeversicherung": [
            {
                "label": "Gesetzlich familienversichert",
                "case_updates": {
                    "krankenversicherung": "familienversichert",
                    "pflegeversicherung_selbst_beitragspflichtig": "nein",
                },
            },
            {
                "label": "Studentisch gesetzlich versichert",
                "case_updates": {
                    "krankenversicherung": "studentisch_gesetzlich",
                    "pflegeversicherung_selbst_beitragspflichtig": "ja",
                },
            },
            {
                "label": "Freiwillig gesetzlich versichert",
                "case_updates": {
                    "krankenversicherung": "freiwillig_gesetzlich",
                    "pflegeversicherung_selbst_beitragspflichtig": "ja",
                },
            },
            {
                "label": "Privat versichert",
                "case_updates": {
                    "krankenversicherung": "privat",
                    "pflegeversicherung_selbst_beitragspflichtig": "ja",
                },
            },
            {
                "label": "Andere Versicherungsform",
                "case_updates": {
                    "krankenversicherung": "anders",
                    "pflegeversicherung_selbst_beitragspflichtig": "ja",
                },
            },
        ],
        "eigenes_einkommen": [
            {
                "label": "Ja, voraussichtlich eigenes Einkommen",
                "case_updates": {"eigenes_einkommen": "ja"},
            },
            {
                "label": "Nein, voraussichtlich kein eigenes Einkommen",
                "case_updates": {"eigenes_einkommen": "nein"},
            },
        ],
        "vermoegen_unter_grenze": [
            {
                "label": "Ja, mein Vermögen liegt unter der genannten Grenze",
                "case_updates": {"vermoegen_unter_grenze": "ja"},
            },
            {
                "label": "Nein, mein Vermögen erreicht oder überschreitet die Grenze",
                "case_updates": {"vermoegen_unter_grenze": "nein"},
            },
        ],
    }

    return options_by_step.get(step_key, [])


def build_choice_result(option: dict[str, Any]) -> dict[str, Any]:
    """Überführt eine angeklickte Option in das Format des LLM-Interpreters."""
    return {
        "intent": "answer",
        "case_updates": dict(option.get("case_updates", {})),
        "profile_updates": dict(option.get("profile_updates", {})),
        "confidence": "high",
        "should_save": True,
        "needs_followup": False,
        "followup_question": "",
        "assistant_answer": "",
        "next_action": "continue",
    }


def option_labels(options: list[dict[str, Any]]) -> list[str]:
    return [
        str(option.get("label", "")).strip()
        for option in options
        if str(option.get("label", "")).strip()
    ]
