import hashlib
import hmac
import html
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import markdown
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from openai import OpenAI

from src.application_flow_manager import ApplicationFlowManager
from src.checklist_manager import ChecklistManager
from src.checklist_view import (
    categorize_checklist,
    render_checklist_items,
)
from src.document_processor import DocumentProcessor
from src.formblatt1_manager import Formblatt1Manager
from src.hybrid_questions import build_choice_result, get_hybrid_options
from src.llm_interpreter import (
    explain_application_step,
    interpret_adaptive_application_message,
    validate_result,
)
from src.pdf_form_filler import PdfFormFiller
from src.rag_pipeline import build_vectorstore, get_relevant_context

st.set_page_config(
    page_title="BAföG KI-Assistent",
    page_icon="📄",
    layout="wide",
)

load_dotenv()

# ---------------------------------------------------------------------------
# Zugangsschutz für die gesamte Anwendung
# ---------------------------------------------------------------------------
APP_ACCESS_PASSWORD = os.getenv(
    "APP_ACCESS_PASSWORD",
    "",
).strip()


def require_app_access() -> None:
    """Zeigt die Anwendung erst nach erfolgreicher Kennworteingabe."""

    if "app_authenticated" not in st.session_state:
        st.session_state["app_authenticated"] = False

    if "app_login_error" not in st.session_state:
        st.session_state["app_login_error"] = ""

    # Bei erfolgreicher Anmeldung wird die Anwendung normal ausgeführt.
    if st.session_state["app_authenticated"]:
        return

    st.title("🔒 Geschützter BAföG-Nutzertest")

    st.write(
        "Dieser Prototyp ist ausschließlich für eingeladene "
        "Testpersonen im Rahmen einer Bachelorarbeit vorgesehen."
    )

    # st.info(
    #     "Bitte verwende ausschließlich die bereitgestellten "
    #     "synthetischen Testdokumente und keine eigenen BAföG-Unterlagen."
    # )

    with st.form("app_access_form"):
        entered_password = st.text_input(
            "Zugangskennwort",
            type="password",
            placeholder="Kennwort eingeben",
        )

        login_clicked = st.form_submit_button(
            "Anwendung öffnen",
            type="primary",
            use_container_width=True,
        )

    if st.session_state["app_login_error"]:
        st.error(st.session_state["app_login_error"])

    if login_clicked:
        if not APP_ACCESS_PASSWORD:
            st.session_state["app_login_error"] = (
                "Für die Anwendung wurde kein APP_ACCESS_PASSWORD "
                "in der .env-Datei festgelegt."
            )
            st.rerun()

        entered_password = str(entered_password).strip()

        if hmac.compare_digest(
            entered_password,
            APP_ACCESS_PASSWORD,
        ):
            st.session_state["app_authenticated"] = True
            st.session_state["app_login_error"] = ""
            st.rerun()

        st.session_state["app_login_error"] = (
            "Das eingegebene Zugangskennwort ist falsch."
        )
        st.rerun()

    # Verhindert, dass der restliche Anwendungscode ausgeführt wird.
    st.stop()


require_app_access()

# Kleine runde Hilfeschaltfläche neben „Schnellauswahl“.
# Die CSS-Regel ist auf den Container mit dem Schlüssel
# hybrid_help_button begrenzt und verändert keine anderen Schaltflächen.
st.markdown(
    """
    <style>
    .st-key-hybrid_help_button button {
        width: 2.15rem !important;
        min-width: 2.15rem !important;
        height: 2.15rem !important;
        min-height: 2.15rem !important;
        padding: 0 !important;
        border-radius: 50% !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-weight: 700 !important;
        line-height: 1 !important;
    }

    .st-key-hybrid_help_button button p {
        margin: 0 !important;
        font-size: 1rem !important;
        line-height: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
KNOWLEDGE_FOLDER = os.getenv("KNOWLEDGE_FOLDER", "data/knowledge")
VECTORSTORE_DIR = os.getenv("VECTORSTORE_DIR", "chroma_db")
FORM_TEMPLATE = Path(os.getenv("FORMBLATT_1_TEMPLATE", "formblatt_1.pdf"))

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
flow_manager = ApplicationFlowManager()
checklist_manager = ChecklistManager()
form_manager = Formblatt1Manager()
document_processor = DocumentProcessor(client=client, model=OPENAI_MODEL)
pdf_filler = PdfFormFiller()


PROFILE_KEYS = {
    "vorname",
    "nachname",
    "geburtsname",
    "geburtsdatum",
    "geburtsort",
    "geschlecht",
    "staatsangehoerigkeit",
    "matrikelnummer",
    "hochschule",
    "ausbildungsort",
    "studiengang",
    "abschlussziel",
    "hochschulsemester",
    "fachsemester",
    "regelstudienzeit",
    "anschrift_strasse",
    "anschrift_hausnummer",
    "anschrift_adresszusatz",
    "anschrift_land",
    "anschrift_plz",
    "anschrift_ort",
    "ausbildung_strasse",
    "ausbildung_hausnummer",
    "ausbildung_adresszusatz",
    "ausbildung_land",
    "ausbildung_plz",
    "ausbildung_ort",
    "telefon",
    "email",
    "iban",
    "geldinstitut",
    "kontoinhaber",
    "steuer_id",
    "bewilligungszeitraum_von",
    "bewilligungszeitraum_bis",
    "elternteil1_nachname",
    "elternteil1_vorname",
    "elternteil2_nachname",
    "elternteil2_vorname",
}

DOCUMENT_TYPES = [
    "studienbescheinigung",
    "identitaetsdokument",
    "vollmacht",
    "lebenslauf",
    "kranken_pflegeversicherungsnachweis",
    "wohnungsnachweis",
    "einkommensnachweis",
    "vermoegensnachweis",
    "leistungsnachweis",
    "unbekannt",
]

DOCUMENT_LABELS = {
    "studienbescheinigung": "Studienbescheinigung",
    "identitaetsdokument": "Personalausweis oder Reisepass",
    "vollmacht": "Vollmacht",
    "lebenslauf": "Lebenslauf",
    "kranken_pflegeversicherungsnachweis": "Kranken- und Pflegeversicherungsnachweis",
    "wohnungsnachweis": "Wohnungsnachweis",
    "einkommensnachweis": "Einkommensnachweis",
    "vermoegensnachweis": "Vermögensnachweis",
    "leistungsnachweis": "Leistungsnachweis",
    "unbekannt": "Unbekanntes Dokument",
}


# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------
def empty_field() -> dict[str, str]:
    return {"value": "", "source": "", "confidence": ""}


def initial_profile() -> dict[str, dict[str, str]]:
    profile = {key: empty_field() for key in PROFILE_KEYS}

    profile["staatsangehoerigkeit"] = {
        "value": "deutsch",
        "source": "scope_deutsche_antragsteller",
        "confidence": "high",
    }
    profile["anschrift_land"] = {
        "value": "DE",
        "source": "scope_inland",
        "confidence": "high",
    }
    profile["ausbildung_land"] = {
        "value": "DE",
        "source": "scope_inland",
        "confidence": "high",
    }

    return profile


def initial_case_state() -> dict[str, dict[str, str]]:
    state = {
        "antragsart": {
            "value": "erstantrag",
            "source": "scope",
            "confidence": "high",
        },
        "ausland": {
            "value": "nein",
            "source": "scope",
            "confidence": "high",
        },
        "formblatt_3_relevant": {
            "value": "ja",
            "source": "scope_standard_case",
            "confidence": "medium",
        },
        "bescheid_empfaenger": {
            "value": "An mich – ständiger Wohnsitz",
            "source": "system_default",
            "confidence": "high",
        },
    }

    for key in [
        "vollzeitausbildung",
        "wohnsituation",
        "wohnraum_eigentum_eltern",
        "familienstand",
        "kinder",
        "krankenversicherung",
        "pflegeversicherung_selbst_beitragspflichtig",
        "eigenes_einkommen",
        "vermoegen_unter_grenze",
        "verhaeltnis_elternteile",
    ]:
        state[key] = empty_field()

    return state


def initial_document_registry() -> dict[str, dict[str, Any]]:
    return {
        document_type: {
            "uploaded": False,
            "filenames": [],
            "confidence": "",
            "extracted_fields": [],
            "summary": "",
            "warnings": [],
        }
        for document_type in DOCUMENT_TYPES
    }


def initialize_state() -> None:
    defaults = {
        "user_profile": initial_profile(),
        "case_state": initial_case_state(),
        "document_registry": initial_document_registry(),
        "chat_history": [],
        "assistant_mode": "beratung",
        "current_step_key": "",
        "last_prompted_step": "",
        "adaptive_hint_shown": False,
        "chat_input_version": 0,
        "uploader_version": 0,
        "processed_file_hashes": {},
        "career_entries": [],
        "career_row_count": 1,
        "manual_form_values": {},
        "form_saved": False,
        "edit_mode": False,
        "form_edit_version": 0,
        "editing_section": "",
        "section_edit_version": 0,
        "same_as_main_address": False,
        "data_conflicts": [],
        "rag_initialized": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()

# ---------------------------------------------------------------------------
# Chatdarstellung
# ---------------------------------------------------------------------------
def append_chat(role: str, content: str) -> None:
    st.session_state["chat_history"].append(
        {"role": role, "content": content}
    )


def render_chat_history(chat_history: list[dict[str, str]]) -> str:
    """Erzeugt die HTML-Ausgabe für den Chatverlauf."""
    message_parts: list[str] = []

    for message in chat_history:
        role = str(message.get("role", "")).strip()
        raw_content = str(message.get("content", ""))
        safe_content = html.escape(raw_content)

        content_html = markdown.markdown(
            safe_content,
            extensions=["extra", "nl2br", "sane_lists"],
        )

        if role == "user":
            message_parts.append(
                f"""
                <div style="
                    background: #f3f4f6;
                    border: 1px solid #e5e7eb;
                    border-radius: 15px;
                    padding: 13px 15px;
                    margin: 10px 0 10px auto;
                    max-width: 88%;
                    box-sizing: border-box;
                    font-family: Arial, sans-serif;
                    line-height: 1.55;
                    color: #111827;
                ">
                    <div style="
                        font-size: 12px;
                        font-weight: 700;
                        color: #4b5563;
                        margin-bottom: 7px;
                    ">Du</div>
                    <div>{content_html}</div>
                </div>
                """
            )

        elif role == "assistant":
            message_parts.append(
                f"""
                <div style="
                    background: #fff7ed;
                    border: 1px solid #fed7aa;
                    border-radius: 15px;
                    padding: 13px 15px;
                    margin: 10px auto 10px 0;
                    max-width: 88%;
                    box-sizing: border-box;
                    font-family: Arial, sans-serif;
                    line-height: 1.55;
                    color: #111827;
                ">
                    <div style="
                        font-size: 12px;
                        font-weight: 700;
                        color: #6b7280;
                        margin-bottom: 7px;
                    ">Assistent</div>
                    <div>{content_html}</div>
                </div>
                """
            )

    return "".join(message_parts)

def build_process_card() -> str:
    """Zeigt den aktuellen Arbeitsmodus oberhalb des Chatfensters an."""
    assistant_mode = st.session_state.get("assistant_mode", "beratung")

    if assistant_mode == "beratung":
        mode_title = "Freie BAföG-Beratung"
        mode_icon = "💬"
        description = (
            "Du kannst allgemeine Fragen zur BAföG-Erstantragstellung stellen."
        )
    elif assistant_mode == "initial_documents":
        mode_title = "BAföG-Erstantrag"
        mode_icon = "📄"
        description = (
            "Bitte lade zuerst deine Studienbescheinigung nach § 9 BAföG "
            "oder Formblatt 02 hoch."
        )
    elif assistant_mode == "adaptive_questions":
        mode_title = "BAföG-Erstantrag"
        mode_icon = "📄"
        description = (
            "Der Assistent ergänzt mit dir nur die Angaben, die nicht aus "
            "deinen Dokumenten erkannt wurden."
        )
    elif assistant_mode == "review":
        mode_title = "BAföG-Erstantrag"
        mode_icon = "🧾"
        description = (
            "Kontrolliere die erkannten Angaben und ergänze noch fehlende "
            "Formularfelder."
        )
    elif assistant_mode == "confirmed":
        mode_title = "BAföG-Erstantrag"
        mode_icon = "✅"
        description = (
            "Die bestätigten Angaben können jetzt für Formblatt 1 verwendet werden."
        )
    else:
        mode_title = "BAföG-Erstantrag"
        mode_icon = "📄"
        description = "Der BAföG-Erstantrag wird vorbereitet."

    return f"""
<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:transparent;">
    <div style="
        background:#ffffff;
        border:1px solid #e5e7eb;
        border-radius:14px;
        padding:10px 14px;
        box-shadow:0 2px 8px rgba(0,0,0,0.04);
        font-family:Arial,sans-serif;
        box-sizing:border-box;
    ">
        <div style="
            display:flex;
            align-items:center;
            gap:7px;
            font-size:15px;
            font-weight:700;
            color:#1f2937;
            margin-bottom:7px;
        ">
            <span>{mode_icon}</span>
            <span>Aktueller Modus: {mode_title}</span>
        </div>
        <div style="font-size:13px;line-height:1.45;color:#4b5563;">
            {description}
        </div>
    </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Datenvergleich, Konflikte und Quellenpriorität
# ---------------------------------------------------------------------------
def confidence_rank(value: str) -> int:
    return {
        "low": 1,
        "medium": 2,
        "high": 3,
    }.get(str(value).strip().lower(), 0)


def get_document_type_from_source(source: str) -> str:
    source = str(source or "").strip()

    if not source.startswith("document:"):
        return source

    parts = source.split(":", 2)
    return parts[1] if len(parts) >= 2 else source


def get_source_priority(field_name: str, source: str) -> int:
    source = str(source or "").strip()
    document_type = get_document_type_from_source(source)

    if source == "user_correction":
        return 1000
    if source == "user_confirmed":
        return 950
    if source == "user_selection":
        return 925
    if source in {"manual_input", "user_answer"}:
        return 900
    if source.startswith("scope"):
        return 800

    field_priorities = {
        "hochschule": {
            "studienbescheinigung": 700,
            "lebenslauf": 300,
        },
        "ausbildungsort": {
            "studienbescheinigung": 700,
            "lebenslauf": 300,
        },
        "studiengang": {
            "studienbescheinigung": 700,
            "lebenslauf": 300,
        },
        "abschlussziel": {
            "studienbescheinigung": 700,
            "lebenslauf": 350,
        },
        "matrikelnummer": {"studienbescheinigung": 750},
        "fachsemester": {"studienbescheinigung": 750},
        "hochschulsemester": {"studienbescheinigung": 750},
        "regelstudienzeit": {"studienbescheinigung": 750},
        "vorname": {
            "identitaetsdokument": 750,
            "studienbescheinigung": 650,
            "lebenslauf": 400,
        },
        "nachname": {
            "identitaetsdokument": 750,
            "studienbescheinigung": 650,
            "lebenslauf": 400,
        },
        "geburtsname": {"identitaetsdokument": 750},
        "geburtsdatum": {
            "identitaetsdokument": 750,
            "studienbescheinigung": 650,
            "lebenslauf": 400,
        },
        "geburtsort": {
            "identitaetsdokument": 750,
            "studienbescheinigung": 650,
        },
        "staatsangehoerigkeit": {"identitaetsdokument": 750},
        "anschrift_strasse": {
            "wohnungsnachweis": 750,
            "identitaetsdokument": 700,
            "lebenslauf": 400,
            "kranken_pflegeversicherungsnachweis": 150,
        },
        "anschrift_hausnummer": {
            "wohnungsnachweis": 750,
            "identitaetsdokument": 700,
            "lebenslauf": 400,
            "kranken_pflegeversicherungsnachweis": 150,
        },
        "anschrift_plz": {
            "wohnungsnachweis": 750,
            "identitaetsdokument": 700,
            "lebenslauf": 400,
            "kranken_pflegeversicherungsnachweis": 150,
        },
        "anschrift_ort": {
            "wohnungsnachweis": 750,
            "identitaetsdokument": 700,
            "lebenslauf": 400,
            "kranken_pflegeversicherungsnachweis": 150,
        },
        "telefon": {"lebenslauf": 500},
        "email": {"lebenslauf": 500},
        "krankenversicherung": {
            "kranken_pflegeversicherungsnachweis": 750,
        },
        "pflegeversicherung_selbst_beitragspflichtig": {
            "kranken_pflegeversicherungsnachweis": 750,
        },
    }

    field_rules = field_priorities.get(field_name, {})

    if document_type in field_rules:
        return field_rules[document_type]
    if source.startswith("document:"):
        return 200
    if source in {"derived", "abgeleitet"}:
        return 100

    return 0


def normalize_comparison_value(field_name: str, value: str) -> str:
    text = str(value or "").strip().lower()

    if not text:
        return ""

    text = text.replace("ß", "ss")
    text = re.sub(r"\s+", " ", text)

    if field_name in {"anschrift_strasse", "ausbildung_strasse"}:
        text = re.sub(
            r"\s+\d+[a-z]?\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = text.replace("straße", "str")
        text = text.replace("strasse", "str")
        text = text.replace("str.", "str")
        return re.sub(r"[\s.,\-_/]+", "", text)

    if field_name == "studiengang":
        text = re.sub(r"\([^)]*\)", "", text)
        text = re.sub(
            r"\b(bachelor of science|bachelor|b\.?\s*sc\.?|bsc)\b",
            "",
            text,
        )
        return re.sub(r"[^a-z0-9äöü]+", "", text)

    if field_name in {
        "fachsemester",
        "hochschulsemester",
        "regelstudienzeit",
        "anschrift_plz",
        "ausbildung_plz",
    }:
        digits = re.sub(r"\D", "", text)
        if field_name in {
            "fachsemester",
            "hochschulsemester",
            "regelstudienzeit",
        } and digits:
            return str(int(digits))
        return digits

    if field_name in {
        "geburtsdatum",
        "bewilligungszeitraum_von",
        "bewilligungszeitraum_bis",
    }:
        return re.sub(r"\D", "", text)

    return re.sub(r"[^a-z0-9äöü]+", "", text)


def values_are_equivalent(
    field_name: str,
    first_value: str,
    second_value: str,
) -> bool:
    first_normalized = normalize_comparison_value(field_name, first_value)
    second_normalized = normalize_comparison_value(field_name, second_value)

    return bool(first_normalized) and first_normalized == second_normalized


def build_conflict_key(
    field_name: str,
    old_value: str,
    new_value: str,
) -> str:
    normalized_values = sorted(
        [
            normalize_comparison_value(field_name, old_value),
            normalize_comparison_value(field_name, new_value),
        ]
    )

    return f"{field_name}|{normalized_values[0]}|{normalized_values[1]}"


def add_unique_data_conflict(
    field_name: str,
    old_value: str,
    new_value: str,
    old_source: str,
    new_source: str,
) -> None:
    conflict_key = build_conflict_key(field_name, old_value, new_value)

    if any(
        conflict.get("conflict_key") == conflict_key
        for conflict in st.session_state["data_conflicts"]
    ):
        return

    st.session_state["data_conflicts"].append(
        {
            "conflict_key": conflict_key,
            "field": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "old_source": old_source,
            "new_source": new_source,
        }
    )


def save_metadata_value(
    container_name: str,
    field_name: str,
    value: str,
    source: str,
    confidence: str,
) -> None:
    value = str(value).strip()

    if not value:
        return

    container = st.session_state[container_name]
    existing = container.get(field_name, empty_field())

    existing_value = str(existing.get("value", "")).strip()
    existing_source = str(existing.get("source", "")).strip()
    existing_confidence = str(existing.get("confidence", "")).strip()

    if existing_source in {"user_confirmed", "user_correction"}:
        return

    existing_priority = get_source_priority(field_name, existing_source)
    new_priority = get_source_priority(field_name, source)

    if existing_value:
        if values_are_equivalent(field_name, existing_value, value):
            should_replace = (
                new_priority > existing_priority
                or (
                    new_priority == existing_priority
                    and confidence_rank(confidence)
                    > confidence_rank(existing_confidence)
                )
            )

            if should_replace:
                container[field_name] = {
                    "value": value,
                    "source": source,
                    "confidence": confidence,
                }
            return

        add_unique_data_conflict(
            field_name=field_name,
            old_value=existing_value,
            new_value=value,
            old_source=existing_source,
            new_source=source,
        )

        if new_priority < existing_priority:
            return

        if (
            new_priority == existing_priority
            and confidence_rank(confidence)
            <= confidence_rank(existing_confidence)
        ):
            return

    container[field_name] = {
        "value": value,
        "source": source,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Dokumentverarbeitung
# ---------------------------------------------------------------------------
def filter_document_warnings(
    document_type: str,
    warnings: Any,
) -> list[str]:
    if not isinstance(warnings, list):
        return []

    today = date.today()
    valid_warnings: list[str] = []

    irrelevant_patterns_by_document = {
        "studienbescheinigung": [
            "vorherige ausbildungsstation",
            "vorherigen ausbildungsstation",
            "frühere ausbildungsstation",
            "früheren ausbildungsstation",
            "keine weiteren angaben zu vorherigen",
            "keine angaben zum beruflichen werdegang",
            "keine angaben zum schulischen werdegang",
            "schulischer und beruflicher werdegang",
            "lebenslauf fehlt",
        ],
        "kranken_pflegeversicherungsnachweis": [
            "keine angaben zum beruflichen werdegang",
            "keine angaben zum studienverlauf",
            "keine angaben zu früheren ausbildungen",
        ],
        "wohnungsnachweis": [
            "keine angaben zum beruflichen werdegang",
            "keine angaben zum studienverlauf",
        ],
    }

    irrelevant_patterns = irrelevant_patterns_by_document.get(
        document_type,
        [],
    )

    for warning in warnings:
        warning_text = str(warning).strip()

        if not warning_text:
            continue

        warning_lower = warning_text.lower()

        if any(pattern in warning_lower for pattern in irrelevant_patterns):
            continue

        if "zukunft" in warning_lower:
            month_year_match = re.search(
                r"\b(0?[1-9]|1[0-2])[./-](\d{4})\b",
                warning_text,
            )

            if month_year_match:
                month = int(month_year_match.group(1))
                year = int(month_year_match.group(2))
                referenced_date = date(year, month, 1)

                if referenced_date <= today:
                    continue

        valid_warnings.append(warning_text)

    return valid_warnings


def apply_document_result(result: dict[str, Any]) -> None:
    document_type = result["document_type"]
    filename = result["filename"]
    source = f"document:{document_type}:{filename}"

    for field_name, payload in result.get("profile_updates", {}).items():
        save_metadata_value(
            "user_profile",
            field_name,
            payload.get("value", ""),
            source,
            payload.get("confidence", "medium"),
        )

    for field_name, payload in result.get("case_updates", {}).items():
        save_metadata_value(
            "case_state",
            field_name,
            payload.get("value", ""),
            source,
            payload.get("confidence", "medium"),
        )

    if result.get("career_entries"):
        extracted_entries = result["career_entries"]

        st.session_state["career_entries"] = extracted_entries
        st.session_state["career_row_count"] = max(
            st.session_state.get("career_row_count", 1),
            len(extracted_entries),
        )

    registry = st.session_state["document_registry"].setdefault(
        document_type,
        initial_document_registry()["unbekannt"].copy(),
    )

    registry["uploaded"] = True

    if filename not in registry["filenames"]:
        registry["filenames"].append(filename)

    registry["confidence"] = result.get("confidence", "medium")
    registry["summary"] = result.get("summary", "")
    registry["warnings"] = filter_document_warnings(
        document_type=document_type,
        warnings=result.get("warnings", []),
    )
    registry["extracted_fields"] = sorted(
        set(registry.get("extracted_fields", []))
        | set(result.get("profile_updates", {}))
        | set(result.get("case_updates", {}))
    )


def process_uploaded_files(uploaded_files) -> bool:
    if not uploaded_files:
        return False

    processed_any = False

    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        digest = hashlib.sha256(file_bytes).hexdigest()

        if digest in st.session_state["processed_file_hashes"]:
            continue

        mime_type = uploaded_file.type or "application/octet-stream"

        with st.spinner(f"{uploaded_file.name} wird analysiert …"):
            try:
                result = document_processor.process(
                    filename=uploaded_file.name,
                    mime_type=mime_type,
                    file_bytes=file_bytes,
                )

                apply_document_result(result)

                st.session_state["processed_file_hashes"][digest] = result
                processed_any = True

            except Exception as exc:
                st.error(
                    f"Fehler bei {uploaded_file.name}: {exc}"
                )

                # Die fehlerhafte Datei wird nicht als verarbeitet gespeichert.
                continue

    # Erst nachdem alle aktuell ausgewählten Dateien verarbeitet wurden,
    # wird die nächste noch offene Frage bestimmt.
    if (
            processed_any
            and st.session_state["document_registry"]
    ["studienbescheinigung"]
            .get("uploaded") is True
    ):
        # Nach jedem neu analysierten Dokument prüfen,
        # ob sich die nächste offene Frage geändert hat.
        #
        # last_prompted_step wird hier bewusst NICHT geleert.
        # Dadurch wird dieselbe Frage nicht mehrfach angezeigt.
        move_to_next_application_step(
            force_message=(
                    st.session_state["assistant_mode"]
                    == "initial_documents"
            )
        )

    return processed_any

# ---------------------------------------------------------------------------
# RAG und Dialogsteuerung
# ---------------------------------------------------------------------------
def get_context(question: str) -> str:
    try:
        return get_relevant_context(question, VECTORSTORE_DIR, k=3)
    except Exception:
        return ""


def answer_general_question(question: str) -> str:
    if client is None:
        return "Kein OpenAI API-Key gefunden."

    context = get_context(question)

    messages = [
        {
            "role": "system",
            "content": (
                "Du beantwortest allgemeine Fragen zur deutschen "
                "BAföG-Erstantragstellung. Antworte klar und verständlich. "
                "Nutze den bereitgestellten Kontext. Wenn der Kontext keine "
                "eindeutige Antwort enthält, sage das offen. Gib keine "
                "rechtsverbindliche Entscheidung ab."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Frage: {question}\n\n"
                f"Kontext aus der BAföG-Wissensbasis:\n{context}"
            ),
        },
    ]

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0,
        max_tokens=600,
    )

    return response.choices[0].message.content


def build_adaptive_question_message(step: dict) -> str:
    include_hint = not st.session_state.get(
        "adaptive_hint_shown",
        False,
    )

    question = flow_manager.build_question_text(
        step=step,
        user_profile=st.session_state["user_profile"],
        include_hint=include_hint,
    )

    if include_hint:
        st.session_state["adaptive_hint_shown"] = True

    return question

def render_hybrid_answer_controls() -> None:
    """Zeigt vertikale Schnellauswahlen und eine kompakte Erklärungshilfe.

    Auswahlklicks werden deterministisch gespeichert. Freitext bleibt parallel
    möglich. Die Fragezeichen-Schaltfläche steht klein und rund direkt neben
    der Überschrift „Schnellauswahl“.
    """
    if st.session_state.get("assistant_mode") != "adaptive_questions":
        return

    current_step = flow_manager.get_step_by_key(
        st.session_state.get("current_step_key", "")
    )
    if current_step is None:
        return

    options = get_hybrid_options(
        current_step.get("key", ""),
        st.session_state["user_profile"],
    )

    title_col, help_col = st.columns([0.91, 0.09])

    with title_col:
        st.markdown("**Schnellauswahl**")

    with help_col:
        with st.container(key="hybrid_help_button"):
            explain_clicked = st.button(
                "?",
                key=(
                    "explain_current_step_"
                    + st.session_state.get("current_step_key", "")
                ),
                help="Frage erklären",
                use_container_width=False,
            )

    if options:
        for index, option in enumerate(options):
            label = str(option.get("label", "")).strip()
            if not label:
                continue

            clicked = st.button(
                label,
                key=(
                    f"hybrid_choice_"
                    f"{st.session_state.get('current_step_key', '')}_"
                    f"{index}"
                ),
                use_container_width=True,
            )

            if clicked:
                result = build_choice_result(option)
                valid, validation_message = validate_result(
                    result,
                    current_step,
                )

                if not valid:
                    st.error(validation_message)
                    return

                append_chat("user", f"Auswahl: {label}")
                apply_interpreter_updates(
                    result,
                    source="user_selection",
                )

                st.session_state["last_prompted_step"] = ""
                move_to_next_application_step()
                st.rerun()

        st.caption(
            "Du kannst eine Option anklicken oder deine Situation "
            "weiterhin frei im Textfeld beschreiben."
        )
    else:
        st.caption(
            "Für diese Frage gibt es keine feste Schnellauswahl. "
            "Bitte antworte im Textfeld."
        )

    if explain_clicked:
        rendered_question = flow_manager.build_question_text(
            current_step,
            st.session_state["user_profile"],
            include_hint=False,
        )
        context_query = (
            f"{rendered_question}\n"
            f"{current_step.get('help', '')}"
        )
        context = get_context(context_query)

        append_chat("user", "Bitte erkläre mir die aktuelle Frage.")

        with st.spinner("Die aktuelle Frage wird erklärt …"):
            answer = explain_application_step(
                client=client,
                model=OPENAI_MODEL,
                current_step=current_step,
                rendered_question=rendered_question,
                user_profile=st.session_state["user_profile"],
                case_state=st.session_state["case_state"],
                available_options=options,
                context=context,
                mode="explain",
            )

        append_chat("assistant", answer)
        st.rerun()

def interpret_simple_step_answer(
        step_key: str,
        user_message: str,
        case_state: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """
    Erkennt eindeutige kurze Antworten ohne zusätzlichen LLM-Aufruf.

    Dadurch werden Formulierungen wie „keine Kinder“
    zuverlässig als kinder = nein gespeichert.
    """
    text = str(user_message or "").strip().lower()

    text = text.replace("ß", "ss")
    text = re.sub(
        r"[^a-z0-9äöü]+",
        " ",
        text,
    )
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if step_key == "wohnsituation_und_eigentum":
        case_state = case_state or {}
        existing_living = str(
            case_state.get("wohnsituation", {}).get("value", "")
        ).strip().lower()

        lives_with_parents = any(
            phrase in text
            for phrase in {
                "ich wohne bei meinen eltern",
                "ich lebe bei meinen eltern",
                "mit meinen eltern zusammen",
                "bei meiner mutter",
                "bei meinem vater",
            }
        ) and not any(
            phrase in text
            for phrase in {
                "nicht bei meinen eltern",
                "eltern leben nicht mit mir",
                "meine eltern leben nicht mit mir",
                "nicht mit meinen eltern",
            }
        )

        not_with_parents = any(
            phrase in text
            for phrase in {
                "nicht bei meinen eltern",
                "nicht mit meinen eltern",
                "meine eltern leben nicht mit mir",
                "eltern leben nicht mit mir",
                "meine eltern wohnen nicht mit mir",
                "alleine",
                "in einer wg",
                "im wohnheim",
                "eigene wohnung",
            }
        ) or bool(
            re.search(
                r"\beltern\b.*\b(?:leben|wohnen)\b.*\bnicht\b.*\bmir\b",
                text,
            )
        ) or bool(
            re.search(
                r"\bnicht\b.*\b(?:mit|bei)\b.*\b(?:meinen|meine)\s+eltern\b",
                text,
            )
        )

        parent_owned = any(
            phrase in text
            for phrase in {
                "gehört meinen eltern",
                "gehoert meinen eltern",
                "wohnung meiner eltern",
                "haus meiner eltern",
                "eigentum meiner eltern",
            }
        ) and "nicht meinen eltern" not in text

        non_parent_owner = any(
            phrase in text
            for phrase in {
                "meinem onkel",
                "meiner tante",
                "meinen grosseltern",
                "meinen großeltern",
                "einem vermieter",
                "dem vermieter",
                "einer anderen person",
                "einem verwandten",
                "nicht meinen eltern",
                "gehört mir",
                "gehoert mir",
            }
        )

        if lives_with_parents:
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "wohnsituation": "bei_eltern",
                    "wohnraum_eigentum_eltern": "nicht_relevant",
                },
                "confidence": "high",
            }

        if not_with_parents and parent_owned:
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "wohnsituation": "nicht_bei_eltern",
                    "wohnraum_eigentum_eltern": "ja",
                },
                "confidence": "high",
            }

        if not_with_parents and non_parent_owner:
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "wohnsituation": "nicht_bei_eltern",
                    "wohnraum_eigentum_eltern": "nein",
                },
                "confidence": "high",
            }

        if existing_living == "nicht_bei_eltern" and parent_owned:
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "wohnsituation": "nicht_bei_eltern",
                    "wohnraum_eigentum_eltern": "ja",
                },
                "confidence": "high",
            }

        if existing_living == "nicht_bei_eltern" and non_parent_owner:
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "wohnsituation": "nicht_bei_eltern",
                    "wohnraum_eigentum_eltern": "nein",
                },
                "confidence": "high",
            }

    if step_key == "kinder":
        negative_answers = {
            "nein",
            "keine",
            "kein kind",
            "keine kinder",
            "ich habe keine",
            "ich habe keine kinder",
            "habe keine",
            "habe keine kinder",
            "noch keine",
            "noch keine kinder",
            "kinderlos",
            "ich bin kinderlos",
        }

        if text in negative_answers:
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "kinder": "nein",
                },
                "confidence": "high",
            }

        positive_answers = {
            "ja",
            "ja ich habe kinder",
            "ich habe kinder",
            "habe kinder",
        }

        has_numbered_child_answer = bool(
            re.search(
                r"\b("
                r"ein|eine|einen|zwei|drei|vier|fünf|"
                r"1|2|3|4|5"
                r")\s+("
                r"kind|kinder|sohn|tochter"
                r")\b",
                text,
            )
        )

        if (
                text in positive_answers
                or has_numbered_child_answer
        ):
            return {
                "should_save": True,
                "profile_updates": {},
                "case_updates": {
                    "kinder": "ja",
                },
                "confidence": "high",
            }

    return None

def move_to_next_application_step(
        force_message: bool = False
) -> None:
    """
    Ermittelt nach der Dokumentenanalyse oder einer Nutzerantwort
    die nächste noch offene Frage.

    Sind keine adaptiven Fragen mehr offen, wechselt der Assistent
    zur Formblatt-Vorschau.
    """

    study_certificate_uploaded = (
        st.session_state["document_registry"]
        ["studienbescheinigung"]
        .get("uploaded") is True
    )

    # Ohne Studienbescheinigung bleibt der Assistent
    # in der Dokumentenphase.
    if not study_certificate_uploaded:
        st.session_state["assistant_mode"] = "initial_documents"
        st.session_state["current_step_key"] = ""
        return

    next_step = flow_manager.get_first_unanswered_step(
        st.session_state["user_profile"],
        st.session_state["case_state"],
    )

    # Es gibt noch eine offene adaptive Frage.
    if next_step is not None:
        step_key = str(next_step.get("key", "")).strip()

        st.session_state["assistant_mode"] = "adaptive_questions"
        st.session_state["current_step_key"] = step_key

        last_prompted_step = st.session_state.get(
            "last_prompted_step",
            "",
        )

        should_show_question = (
            force_message
            or last_prompted_step != step_key
        )

        if should_show_question:
            question_message = build_adaptive_question_message(
                next_step
            )

            append_chat(
                "assistant",
                question_message,
            )

            st.session_state["last_prompted_step"] = step_key

        return

    # Keine adaptive Frage mehr offen:
    # Zur kontrollierbaren Vorschau wechseln.
    st.session_state["assistant_mode"] = "review"
    st.session_state["current_step_key"] = ""

    draft = form_manager.build_draft(
        user_profile=st.session_state["user_profile"],
        case_state=st.session_state["case_state"],
        career_entries=st.session_state["career_entries"],
        career_row_count=st.session_state.get(
            "career_row_count",
            1,
        ),
        manual_values=st.session_state["manual_form_values"],
    )

    progress = form_manager.calculate_progress(
        draft
    )

    open_required_fields = form_manager.get_open_fields(
        draft,
        required_only=True,
    )

    missing_field_names = ", ".join(
        str(field.get("label", "")).strip()
        for field in open_required_fields[:6]
        if str(field.get("label", "")).strip()
    )

    # Abschlussmeldung nicht mehrfach in den Chat schreiben.
    if st.session_state.get(
            "last_prompted_step"
    ) == "__review__":
        return

    message = (
        "Die adaptive Dokument- und Fragephase ist abgeschlossen.\n\n"
        f"Ich habe **{progress['filled']} von "
        f"{progress['total']} unterstützten Feldern** vorbereitet. "
        f"Bei den markierten Pflichtfeldern fehlen noch "
        f"{progress['required_open']} Angaben."
    )

    if missing_field_names:
        message += (
            "\n\nBitte ergänze in der Vorschau insbesondere: "
            f"{missing_field_names}."
        )

    message += (
        "\n\nKontrolliere die erkannten Angaben, korrigiere Fehler "
        "und ergänze fehlende Felder. Anschließend kannst du die "
        "Angaben speichern und Formblatt 1 als PDF vorausfüllen."
    )

    append_chat(
        "assistant",
        message,
    )

    st.session_state["last_prompted_step"] = "__review__"

def apply_interpreter_updates(
    result: dict[str, Any],
    source: str = "user_answer",
) -> None:
    for field_name, value in result.get("profile_updates", {}).items():
        save_metadata_value(
            "user_profile",
            field_name,
            value,
            source,
            result.get("confidence", "medium"),
        )

    for field_name, value in result.get("case_updates", {}).items():
        save_metadata_value(
            "case_state",
            field_name,
            value,
            source,
            result.get("confidence", "medium"),
        )


def reset_application() -> None:
    """
    Löscht alle Daten des aktuellen BAföG-Antrags.

    Der allgemeine Chatverlauf wird hier noch nicht gelöscht,
    damit die Funktion auch beim Start eines neuen Antrags
    verwendet werden kann.
    """
    st.session_state["user_profile"] = initial_profile()
    st.session_state["case_state"] = initial_case_state()
    st.session_state["document_registry"] = initial_document_registry()
    st.session_state["processed_file_hashes"] = {}
    st.session_state["career_entries"] = []
    st.session_state["career_row_count"] = 1
    st.session_state["manual_form_values"] = {}

    st.session_state["form_saved"] = False
    st.session_state["edit_mode"] = False
    st.session_state["form_edit_version"] = 0
    st.session_state["editing_section"] = ""
    st.session_state["section_edit_version"] = 0
    st.session_state["same_as_main_address"] = False

    st.session_state["data_conflicts"] = []

    st.session_state["current_step_key"] = ""
    st.session_state["last_prompted_step"] = ""
    st.session_state["adaptive_hint_shown"] = False

    # Neues leeres Eingabefeld erzeugen
    st.session_state["chat_input_version"] += 1

    # Neuen leeren Dateiuploader erzeugen
    st.session_state["uploader_version"] += 1

    st.session_state["assistant_mode"] = "initial_documents"

def clear_chat_and_application() -> None:
    """
    Löscht den Chat, alle hochgeladenen Nachweise,
    alle extrahierten Angaben und die Formblatt-Vorschau.
    """
    st.session_state["chat_history"] = []

    reset_application()

    # Nach dem vollständigen Löschen zurück
    # zur freien BAföG-Beratung wechseln.
    st.session_state["assistant_mode"] = "beratung"
    st.session_state["current_step_key"] = ""
    st.session_state["last_prompted_step"] = ""
    st.session_state["adaptive_hint_shown"] = False

def start_application_callback() -> None:
    """Startet den dokumentenbasierten BAföG-Erstantrag."""
    reset_application()

    append_chat(
            "assistant",
            (
                "Wir beginnen dokumentenbasiert. Bitte lade zuerst deine "
                "**Studienbescheinigung nach § 9 BAföG oder Formblatt 02** hoch.\n\n"
                "Optional kannst du gleichzeitig weitere Dokumente hochladen, "
                "damit ich möglichst viele Angaben automatisch übernehme:\n"
                "- Personalausweis oder Reisepass\n"
                "- Lebenslauf\n"
                "- Bescheinigung über Kranken- und Pflegeversicherung\n"
                "- Wohnungsnachweis\n"
                "- Einkommensnachweis\n\n"
                "Nach der Analyse frage ich automatisch nur noch die Angaben ab, "
                "die nicht aus deinen Dokumenten erkannt wurden."
            ),
        )

# ---------------------------------------------------------------------------
# Checkliste
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Formblatt-Vorschau
# ---------------------------------------------------------------------------
def format_field_source(source: str) -> str:
    source = str(source or "").strip()

    if not source:
        return "Noch keine Quelle"

    if source.startswith("document:"):
        parts = source.split(":", 2)
        document_type = parts[1] if len(parts) > 1 else ""
        filename = parts[2] if len(parts) > 2 else ""
        label = DOCUMENT_LABELS.get(
            document_type,
            document_type.replace("_", " ").title(),
        )
        return f"{label} – {filename}" if filename else label

    source_labels = {
        "user_answer": "Antwort im Chat",
        "user_selection": "Auswahl im Hybrid-Dialog",
        "user_confirmed": "Vom Nutzer bestätigt",
        "user_correction": "Vom Nutzer korrigiert",
        "manual_input": "Manuelle Eingabe",
        "scope": "Festgelegter Prototypumfang",
        "scope_inland": "Festgelegter Prototypumfang",
        "scope_deutsche_antragsteller": "Festgelegter Prototypumfang",
        "scope_standard_case": "Systemvorgabe für den Standardfall",
        "system_default_no_birth_name": (
            "Systemvorgabe: kein abweichender Geburtsname angegeben"
        ),
        "derived_applicant_name": (
            "Aus Vor- und Nachname der antragstellenden Person übernommen"
        ),
        "copied_main_address": "Vom ständigen Wohnsitz übernommen",
        "derived": "Vom System abgeleitet",
        "abgeleitet": "Vom System abgeleitet",
    }

    return source_labels.get(
        source,
        source.replace("_", " ").title(),
    )


def format_confidence(confidence: str) -> str:
    return {
        "high": "hoch",
        "medium": "mittel",
        "low": "niedrig",
    }.get(str(confidence or "").lower(), "-")


def build_readonly_widget_key(field_id: str, field: dict) -> str:
    key_content = (
        f"{field_id}|"
        f"{field.get('value', '')}|"
        f"{field.get('source', '')}|"
        f"{field.get('status', '')}"
    )

    value_hash = hashlib.sha256(
        key_content.encode("utf-8")
    ).hexdigest()[:12]

    return f"readonly_{field_id}_{value_hash}"


def build_form_field_help(field: dict) -> str:
    help_parts = [
        f"Quelle: {format_field_source(field.get('source', ''))}",
        f"Sicherheit: {format_confidence(field.get('confidence', ''))}",
        f"Status: {field.get('status', 'offen')}",
    ]

    if field.get("help"):
        help_parts.append(str(field["help"]))

    return "\n".join(help_parts)


def render_disabled_form_preview(draft: dict) -> None:
    current_section = None

    for field_id, field in draft.items():
        section = str(
            field.get("section", "Weitere Angaben")
        ).strip()

        if current_section != section:
            current_section = section
            st.markdown(f"### {current_section}")

        label = str(field.get("label", field_id))

        if field.get("required") is True:
            label += " *"

        current_value = str(field.get("value", "")).strip()
        help_text = build_form_field_help(field)
        widget_key = build_readonly_widget_key(field_id, field)

        if field.get("input_type") == "select":
            options = [
                str(option)
                for option in (field.get("options") or [""])
            ]

            if current_value not in options:
                options = [current_value, *options]

            current_index = (
                options.index(current_value)
                if current_value in options
                else 0
            )

            st.selectbox(
                label=label,
                options=options,
                index=current_index,
                disabled=True,
                help=help_text,
                key=widget_key,
            )
        else:
            st.text_input(
                label=label,
                value=current_value,
                disabled=True,
                help=help_text,
                key=widget_key,
            )



def group_draft_by_section(draft: dict) -> dict[str, list[tuple[str, dict]]]:
    sections: dict[str, list[tuple[str, dict]]] = {}
    for field_id, field in draft.items():
        section = str(field.get("section", "Weitere Angaben")).strip()
        sections.setdefault(section, []).append((field_id, field))
    return sections


def calculate_section_progress(
    section_fields: list[tuple[str, dict]],
) -> dict[str, Any]:
    """Berechnet den tatsächlichen Füllstand einer Formularkategorie.

    Eine Kategorie ist nur dann vollständig, wenn alle aktuell unterstützten
    Felder dieser Kategorie befüllt sind. Sind nur einzelne Angaben vorhanden,
    wird sie als teilweise markiert. Fehlende Pflichtfelder führen immer zum
    Status unvollständig.
    """
    required_fields = [
        field
        for _, field in section_fields
        if field.get("required") is True
    ]

    required_filled = sum(
        1
        for field in required_fields
        if str(field.get("value", "")).strip()
    )
    required_open = len(required_fields) - required_filled

    total = len(section_fields)
    filled = sum(
        1
        for _, field in section_fields
        if str(field.get("value", "")).strip()
    )

    all_filled = total > 0 and filled == total

    return {
        "complete": all_filled,
        "required_complete": required_open == 0,
        "required_total": len(required_fields),
        "required_filled": required_filled,
        "required_open": required_open,
        "total": total,
        "filled": filled,
    }


def get_section_status(
    section_progress: dict[str, Any],
) -> dict[str, str]:
    """Liefert Status, Symbol und Badge-Farben aus einer gemeinsamen Quelle."""
    if section_progress["complete"]:
        return {
            "text": "Vollständig",
            "icon": "🟢",
            "background": "#dcfce7",
            "foreground": "#166534",
            "border": "#86efac",
        }

    if (
        section_progress["filled"] > 0
        and section_progress["required_open"] == 0
    ):
        return {
            "text": "Teilweise",
            "icon": "🟡",
            "background": "#fef3c7",
            "foreground": "#92400e",
            "border": "#fcd34d",
        }

    return {
        "text": "Unvollständig",
        "icon": "🔴",
        "background": "#fee2e2",
        "foreground": "#991b1b",
        "border": "#fca5a5",
    }


def render_section_status_badge(
    section_progress: dict[str, Any],
) -> None:
    status = get_section_status(section_progress)

    st.markdown(
        f"""
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:{status['background']};
            color:{status['foreground']};
            border:1px solid {status['border']};
            font-size:0.82rem;
            font-weight:700;
            margin-bottom:0.45rem;
        ">{status['text']}</span>
        """,
        unsafe_allow_html=True,
    )

    if section_progress["required_open"] > 0:
        st.caption(
            f"{section_progress['filled']} von "
            f"{section_progress['total']} Feldern vorbereitet · "
            f"{section_progress['required_open']} Pflichtfelder fehlen"
        )
    elif section_progress["complete"]:
        st.caption(
            f"Alle {section_progress['total']} unterstützten Felder "
            "dieser Kategorie sind ausgefüllt."
        )
    else:
        st.caption(
            f"{section_progress['filled']} von "
            f"{section_progress['total']} unterstützten Feldern vorbereitet. "
            "Die noch offenen Felder sind aktuell nicht als Pflichtfelder markiert."
        )

def render_form_field_widget(
    field_id: str,
    field: dict,
    editable: bool,
    widget_key: str,
) -> str:
    label = str(field.get("label", field_id))
    if field.get("required") is True:
        label += " *"

    current_value = str(field.get("value", ""))
    help_text = build_form_field_help(field)

    if field.get("input_type") == "select":
        options = [
            str(option)
            for option in (field.get("options") or [""])
        ]
        if current_value not in options:
            options = [current_value, *options]

        current_index = (
            options.index(current_value)
            if current_value in options
            else 0
        )

        return st.selectbox(
            label=label,
            options=options,
            index=current_index,
            disabled=not editable,
            help=help_text,
            key=widget_key,
        )

    return st.text_input(
        label=label,
        value=current_value,
        disabled=not editable,
        help=help_text,
        key=widget_key,
    )


MAIN_TO_TRAINING_ADDRESS_FIELDS = {
    "anschrift_strasse": "ausbildung_strasse",
    "anschrift_hausnummer": "ausbildung_hausnummer",
    "anschrift_land": "ausbildung_land",
    "anschrift_plz": "ausbildung_plz",
    "anschrift_ort": "ausbildung_ort",
}


def copy_main_address_to_training_address(
    main_values: dict[str, str] | None = None,
) -> bool:
    """Übernimmt die aktuelle Hauptanschrift in die Ausbildungsanschrift.

    Es werden die bereits angezeigten Draft-Werte verwendet. Dadurch werden
    auch manuelle Korrekturen aus der Kategorie „Ständiger Wohnsitz“
    berücksichtigt. Die Funktion liefert True, wenn sich Werte geändert haben.
    """
    if main_values is None:
        current_draft = form_manager.build_draft(
            user_profile=st.session_state["user_profile"],
            case_state=st.session_state["case_state"],
            career_entries=st.session_state["career_entries"],
            career_row_count=st.session_state.get(
                "career_row_count",
                1,
            ),
            manual_values=st.session_state["manual_form_values"],
        )
        main_values = {
            field_id: str(
                current_draft.get(field_id, {}).get("value", "")
            ).strip()
            for field_id in MAIN_TO_TRAINING_ADDRESS_FIELDS
        }

    merged_values = dict(
        st.session_state.get("manual_form_values", {})
    )
    changed = False

    for main_field, training_field in MAIN_TO_TRAINING_ADDRESS_FIELDS.items():
        new_value = str(main_values.get(main_field, "")).strip()
        old_value = str(merged_values.get(training_field, "")).strip()

        if old_value != new_value:
            merged_values[training_field] = new_value
            changed = True

    if changed:
        st.session_state["manual_form_values"] = merged_values
        st.session_state["form_saved"] = False

    return changed


def sync_training_address_checkbox() -> None:
    """Callback für „Gleich wie ständiger Wohnsitz“."""
    if st.session_state.get("same_as_main_address") is True:
        copy_main_address_to_training_address()


def render_categorized_form_preview(draft: dict) -> None:
    sections = group_draft_by_section(draft)
    editing_section = st.session_state.get("editing_section", "")

    st.markdown("### Status und Angaben nach Kategorien")
    st.caption(
        "Klappe eine Kategorie auf, um die enthaltenen Angaben zu prüfen. "
        "Grün bedeutet vollständig, Gelb teilweise ausgefüllt und Rot "
        "unvollständig beziehungsweise mit fehlenden Pflichtangaben."
    )

    for section, section_fields in sections.items():
        section_progress = calculate_section_progress(section_fields)
        section_status = get_section_status(section_progress)
        is_editing = editing_section == section

        with st.expander(
            (
                f"{section} · "
                f"{section_status['icon']} {section_status['text']}"
            ),
            expanded=is_editing,
        ):
            render_section_status_badge(section_progress)

            same_address_active = False
            if section == "Anschrift während der Ausbildung":
                same_address_active = st.checkbox(
                    "Gleich wie ständiger Wohnsitz",
                    key="same_as_main_address",
                    help=(
                        "Übernimmt Straße, Hausnummer, Land, Postleitzahl "
                        "und Ort aus der Kategorie „Ständiger Wohnsitz“."
                    ),
                    on_change=sync_training_address_checkbox,
                )

                if same_address_active:
                    st.caption(
                        "Die Anschrift wurde vom ständigen Wohnsitz übernommen. "
                        "Entferne das Häkchen, um eine andere Ausbildungsanschrift "
                        "einzutragen."
                    )

            if not is_editing:
                for field_id, field in section_fields:
                    widget_key = build_readonly_widget_key(
                        f"{section}_{field_id}",
                        field,
                    )
                    render_form_field_widget(
                        field_id=field_id,
                        field=field,
                        editable=False,
                        widget_key=widget_key,
                    )

                if (
                    section == "Anschrift während der Ausbildung"
                    and same_address_active
                ):
                    st.info(
                        "Diese Kategorie wird automatisch aus dem ständigen "
                        "Wohnsitz befüllt. Entferne zuerst das Häkchen, wenn du "
                        "abweichende Angaben eintragen möchtest."
                    )
                elif st.button(
                    "Kategorie bearbeiten",
                    key=(
                        "edit_section_"
                        + hashlib.sha256(
                            section.encode("utf-8")
                        ).hexdigest()[:10]
                    ),
                    use_container_width=True,
                ):
                    st.session_state["editing_section"] = section
                    st.session_state["section_edit_version"] += 1
                    st.session_state["form_saved"] = False
                    st.rerun()

                continue

            edit_version = st.session_state["section_edit_version"]
            section_hash = hashlib.sha256(
                section.encode("utf-8")
            ).hexdigest()[:10]
            edited_values: dict[str, str] = {}

            st.info(
                "Bearbeitungsmodus für diese Kategorie: Ergänze oder "
                "korrigiere die Angaben und speichere anschließend."
            )

            with st.form(
                f"section_edit_form_{section_hash}_{edit_version}"
            ):
                for field_id, field in section_fields:
                    edited_values[field_id] = render_form_field_widget(
                        field_id=field_id,
                        field=field,
                        editable=True,
                        widget_key=(
                            f"section_edit_{section_hash}_"
                            f"{edit_version}_{field_id}"
                        ),
                    )

                add_career_entry = False

                if section == "Schulischer und beruflicher Werdegang":
                    add_col, save_col, cancel_col = st.columns(
                        [1.25, 1, 1]
                    )

                    add_career_entry = add_col.form_submit_button(
                        "➕ Weitere Station",
                        use_container_width=True,
                        disabled=(
                                st.session_state.get(
                                    "career_row_count",
                                    1,
                                )
                                >= 8
                        ),
                    )
                else:
                    save_col, cancel_col = st.columns(2)

                save_section = save_col.form_submit_button(
                    "Kategorie speichern",
                    use_container_width=True,
                )

                cancel_section = cancel_col.form_submit_button(
                    "Abbrechen",
                    use_container_width=True,
                )

            if add_career_entry:
                # Bereits eingegebene Werte sichern, bevor eine neue
                # Station erzeugt und die Seite neu geladen wird.
                merged_values = dict(
                    st.session_state.get(
                        "manual_form_values",
                        {},
                    )
                )

                merged_values.update(
                    {
                        field_id: str(value).strip()
                        for field_id, value in edited_values.items()
                    }
                )

                st.session_state["manual_form_values"] = merged_values

                current_count = st.session_state.get(
                    "career_row_count",
                    1,
                )

                st.session_state["career_row_count"] = min(
                    current_count + 1,
                    8,
                )

                # Kategorie bleibt im Bearbeitungsmodus.
                st.session_state["section_edit_version"] += 1
                st.session_state["form_saved"] = False

                st.rerun()

            elif cancel_section:
                st.session_state["editing_section"] = ""
                st.rerun()


            elif save_section:
                merged_values = dict(
                    st.session_state.get(
                        "manual_form_values",
                        {},
                    )
                )
                merged_values.update(
                    {
                        field_id: str(value).strip()
                        for field_id, value in edited_values.items()
                    }
                )

                st.session_state["manual_form_values"] = merged_values
                if "bescheid_empfaenger" in edited_values:
                    selected_recipient = str(
                        edited_values["bescheid_empfaenger"]
                    ).strip()

                    st.session_state["case_state"]["bescheid_empfaenger"] = {
                        "value": selected_recipient,
                        "source": "user_confirmed",
                        "confidence": "high",
                    }

                st.session_state["editing_section"] = ""

                st.session_state["form_saved"] = False

                st.toast(
                    f"Kategorie „{section}“ wurde gespeichert."
                )

                st.rerun()


# ---------------------------------------------------------------------------
# Abmelden und aktuelle Sitzungsdaten löschen
# ---------------------------------------------------------------------------
if "logout_confirmation_visible" not in st.session_state:
    st.session_state["logout_confirmation_visible"] = False


# Obere Abmeldeschaltfläche gestalten.
st.markdown(
    """
    <style>
    .st-key-top_logout_bar {
        position: sticky;
        top: 0.4rem;
        z-index: 1000;

        background: rgba(255, 255, 255, 0.96);
        backdrop-filter: blur(8px);

        padding: 0.35rem 0 0.55rem 0;
        margin-bottom: 0.6rem;

        border-bottom: 1px solid #e5e7eb;
    }

    .st-key-top_logout_bar button {
        border: 1px solid #ef4444 !important;
        color: #b91c1c !important;
        background: #ffffff !important;
        font-weight: 600 !important;
    }

    .st-key-top_logout_bar button:hover {
        background: #fef2f2 !important;
        border-color: #dc2626 !important;
        color: #991b1b !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


with st.container(key="top_logout_bar"):
    spacer_col, logout_col = st.columns(
        [0.68, 0.32]
    )

    with logout_col:
        logout_clicked = st.button(
            "🚪 Abmelden und Sitzungsdaten löschen",
            key="show_logout_confirmation",
            use_container_width=True,
        )

    if logout_clicked:
        st.session_state["logout_confirmation_visible"] = True
        st.rerun()


# Sicherheitsabfrage, damit die Daten nicht versehentlich gelöscht werden.
if st.session_state["logout_confirmation_visible"]:
    with st.container(border=True):
        st.markdown("### Sitzung wirklich beenden?")

        st.warning(
            "Beim Abmelden werden alle Daten der aktuellen Sitzung gelöscht. "
            "Dazu gehören der Chatverlauf, hochgeladene Nachweise, erkannte "
            "Angaben, Formularwerte und die Administrator-Anmeldung."
        )

        confirm_col, cancel_col = st.columns(2)

        confirm_logout = confirm_col.button(
            "Ja, abmelden und Daten löschen",
            type="primary",
            key="confirm_complete_logout",
            use_container_width=True,
        )

        cancel_logout = cancel_col.button(
            "Abbrechen",
            key="cancel_complete_logout",
            use_container_width=True,
        )

        if confirm_logout:
            # Löscht sämtliche Daten dieser Browser-Sitzung.
            st.session_state.clear()

            # Danach erscheint erneut die App-Kennwortanmeldung.
            st.rerun()

        if cancel_logout:
            st.session_state["logout_confirmation_visible"] = False
            st.rerun()

# ---------------------------------------------------------------------------
# Kopfbereich
# ---------------------------------------------------------------------------
st.title("📄 BAföG KI-Assistent – dokumentenbasierter Erstantrag")

st.caption(
    "Abgrenzung des Prototyps: deutsche Antragsteller, BAföG-Erstantrag "
    "und Studium in Deutschland. Die Ausgabe ist eine prototypische "
    "Vorbereitung und keine rechtsverbindliche Entscheidung."
)

# ---------------------------------------------------------------------------
# Geschützter Administratorbereich
# ---------------------------------------------------------------------------
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

if "admin_login_visible" not in st.session_state:
    st.session_state["admin_login_visible"] = False

if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False

if "admin_login_error" not in st.session_state:
    st.session_state["admin_login_error"] = ""


admin_button_col, spacer_col = st.columns([0.18, 0.82])

with admin_button_col:
    admin_button_clicked = st.button(
        "🔐 Admin",
        key="open_admin_login",
        use_container_width=True,
    )

if admin_button_clicked:
    st.session_state["admin_login_visible"] = True
    st.session_state["admin_login_error"] = ""


if (
    st.session_state["admin_login_visible"]
    and not st.session_state["admin_authenticated"]
):
    with st.container(border=True):
        st.markdown("### 🔐 Administrator-Anmeldung")

        st.caption(
            "Dieser Bereich ist ausschließlich für die Verwaltung "
            "der BAföG-Wissensbasis vorgesehen."
        )

        admin_password_input = st.text_input(
            "Administrator-Kennwort",
            type="password",
            key="admin_password_input",
            placeholder="Kennwort eingeben",
        )

        login_col, cancel_col = st.columns(2)

        admin_login_clicked = login_col.button(
            "Anmelden",
            type="primary",
            key="admin_login_button",
            use_container_width=True,
        )

        admin_cancel_clicked = cancel_col.button(
            "Abbrechen",
            key="admin_login_cancel",
            use_container_width=True,
        )

        if st.session_state["admin_login_error"]:
            st.error(st.session_state["admin_login_error"])

        if admin_cancel_clicked:
            st.session_state["admin_login_visible"] = False
            st.session_state["admin_login_error"] = ""
            st.session_state.pop("admin_password_input", None)
            st.rerun()

        if admin_login_clicked:
            if not ADMIN_PASSWORD:
                st.session_state["admin_login_error"] = (
                    "Es wurde kein ADMIN_PASSWORD in der .env-Datei festgelegt."
                )
                st.rerun()

            entered_password = str(admin_password_input).strip()

            if hmac.compare_digest(
                entered_password,
                ADMIN_PASSWORD,
            ):
                st.session_state["admin_authenticated"] = True
                st.session_state["admin_login_visible"] = False
                st.session_state["admin_login_error"] = ""
                st.session_state.pop("admin_password_input", None)
                st.rerun()

            else:
                st.session_state["admin_login_error"] = (
                    "Das eingegebene Administrator-Kennwort ist falsch."
                )
                st.rerun()


if st.session_state["admin_authenticated"]:
    with st.expander(
        "📚 Administratorbereich",
        expanded=True,
    ):
        st.success("Du bist als Administrator angemeldet.")

        st.write(
            "Hier kannst du die lokale RAG-Wissensbasis "
            "des BAföG-Assistenten neu aufbauen."
        )

        rebuild_clicked = st.button(
            "Wissensbasis neu aufbauen",
            key="rebuild_knowledge_base",
            use_container_width=True,
        )

        if rebuild_clicked:
            try:
                with st.spinner(
                    "Wissensbasis wird neu aufgebaut …"
                ):
                    build_vectorstore(
                        KNOWLEDGE_FOLDER,
                        VECTORSTORE_DIR,
                    )

                st.session_state["rag_initialized"] = True

                st.success(
                    "Die Wissensbasis wurde erfolgreich neu aufgebaut."
                )

            except Exception as exc:  # noqa: BLE001
                st.session_state["rag_initialized"] = False

                st.error(
                    "Die Wissensbasis konnte nicht neu aufgebaut werden: "
                    f"{exc}"
                )

        logout_clicked = st.button(
            "Administrator abmelden",
            key="admin_logout_button",
            use_container_width=True,
        )

        if logout_clicked:
            st.session_state["admin_authenticated"] = False
            st.session_state["admin_login_visible"] = False
            st.session_state["admin_login_error"] = ""
            st.session_state.pop("admin_password_input", None)
            st.rerun()

# ---------------------------------------------------------------------------
# Hauptlayout
# ---------------------------------------------------------------------------
left_col, right_col = st.columns(
    [1.15, 0.85],
    gap="large",
)

application_mode_active = (
    st.session_state.get(
        "assistant_mode",
        "beratung",
    )
    in {
        "initial_documents",
        "adaptive_questions",
        "review",
        "confirmed",
    }
)

# ---------------------------------------------------------------------------
# Chat und Prozesssteuerung
# ---------------------------------------------------------------------------
with left_col:
    st.subheader("💬 Chatbot")

    components.html(
        build_process_card(),
        height=88,
        scrolling=False,
    )

    chat_history = st.session_state["chat_history"]

    chat_html = render_chat_history(
        chat_history
    )

    # Bei einem leeren Chat kompakter darstellen.
    chat_container_height = (
        320
        if not chat_history
        else 480
    )

    empty_chat_html = """
        <div style="
            height:100%;
            display:flex;
            align-items:center;
            justify-content:center;
            color:#9ca3af;
            font-family:Arial,sans-serif;
            text-align:center;
            box-sizing:border-box;
        ">
            Noch keine Nachrichten vorhanden.
        </div>
    """

    components.html(
        f"""
        <div id="chat-container" style="
            height:{chat_container_height}px;
            overflow-y:auto;
            border:1px solid #e5e7eb;
            border-radius:16px;
            padding:14px;
            background:#ffffff;
            box-sizing:border-box;
            scroll-behavior:smooth;
        ">
            {chat_html if chat_html else empty_chat_html}
        </div>

        <script>
            const chatContainer = document.getElementById("chat-container");

            if (chatContainer) {{
                setTimeout(() => {{
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }}, 50);
            }}
        </script>
        """,
        height=chat_container_height + 10,
        scrolling=False,
    )

    chat_input_version = st.session_state[
        "chat_input_version"
    ]

    render_hybrid_answer_controls()

    user_message = st.text_area(
        "Nachricht",
        placeholder=(
            "Stelle eine allgemeine BAföG-Frage oder antworte frei "
            "auf die aktuelle Frage."
        ),
        height=100,
        key=f"chat_input_text_{chat_input_version}",
    )

    btn_send, btn_clear = st.columns(2)

    send_clicked = btn_send.button(
        "Nachricht senden",
        use_container_width=True,
    )

    clear_clicked = btn_clear.button(
        "Chat und Antrag löschen",
        use_container_width=True,
    )

    if clear_clicked:
        clear_chat_and_application()
        st.rerun()

    if send_clicked:
        message = user_message.strip()

        if not message:
            st.warning("Bitte gib eine Nachricht ein.")
        elif client is None:
            st.error("Kein OPENAI_API_KEY gefunden.")
        else:
            append_chat("user", message)
            mode = st.session_state["assistant_mode"]

            if mode == "beratung":
                with st.spinner("Antwort wird erstellt …"):
                    append_chat(
                        "assistant",
                        answer_general_question(message),
                    )

            elif mode == "initial_documents":
                if "?" in message or any(
                    word in message.lower()
                    for word in ["was", "warum", "welche", "wie"]
                ):
                    with st.spinner("Antwort wird erstellt …"):
                        answer = answer_general_question(message)

                    append_chat(
                        "assistant",
                        answer
                        + "\n\nFür den Antragsassistenten brauche ich weiterhin "
                        "zuerst die Studienbescheinigung oder Formblatt 02.",
                    )
                else:
                    append_chat(
                        "assistant",
                        "Bitte lade zuerst die Studienbescheinigung oder "
                        "Formblatt 02 im Upload-Bereich hoch.",
                    )

            elif mode == "adaptive_questions":
                current_step = flow_manager.get_step_by_key(
                    st.session_state["current_step_key"]
                )

                if current_step is None:
                    move_to_next_application_step(
                        force_message=True
                    )

                else:
                    direct_result = interpret_simple_step_answer(
                        step_key=current_step["key"],
                        user_message=message,
                        case_state=st.session_state["case_state"],
                    )

                    # Eindeutige Antworten direkt speichern,
                    # ohne sie nochmals vom LLM interpretieren zu lassen.
                    if direct_result is not None:
                        apply_interpreter_updates(direct_result)

                        st.session_state["last_prompted_step"] = ""

                        move_to_next_application_step()

                    else:
                        rendered_question = flow_manager.build_question_text(
                            current_step,
                            st.session_state["user_profile"],
                            include_hint=False,
                        )

                        context = get_context(
                            f"{rendered_question}\nNutzerrückfrage oder Antwort: {message}"
                        )

                        with st.spinner(
                                "Antwort wird interpretiert …"
                        ):
                            result = interpret_adaptive_application_message(
                                client=client,
                                model=OPENAI_MODEL,
                                user_message=message,
                                current_step=current_step,
                                rendered_question=rendered_question,
                                user_profile=st.session_state["user_profile"],
                                case_state=st.session_state["case_state"],
                                context=context,
                                available_options=get_hybrid_options(
                                    current_step.get("key", ""),
                                    st.session_state["user_profile"],
                                ),
                            )

                        if result.get("should_save") is True:
                            valid, validation_message = validate_result(
                                result,
                                current_step,
                            )

                            if valid:
                                apply_interpreter_updates(result)
                                st.session_state["last_prompted_step"] = ""
                                move_to_next_application_step()

                            else:
                                append_chat(
                                    "assistant",
                                    (
                                        "Ich konnte die Angabe noch nicht sicher speichern. "
                                        f"{validation_message}\n\n"
                                        f"{rendered_question}"
                                    ),
                                )

                        else:
                            answer_parts: list[str] = []

                            assistant_answer = str(
                                result.get("assistant_answer", "")
                            ).strip()
                            followup_question = str(
                                result.get("followup_question", "")
                            ).strip()

                            if assistant_answer:
                                answer_parts.append(assistant_answer)

                            if (
                                followup_question
                                and followup_question != assistant_answer
                            ):
                                answer_parts.append(followup_question)

                            append_chat(
                                "assistant",
                                "\n\n".join(answer_parts)
                                or rendered_question,
                            )

            else:
                with st.spinner("Antwort wird erstellt …"):
                    answer = answer_general_question(message)

                append_chat(
                    "assistant",
                    answer
                    + "\n\nDie Formblatt-Vorschau befindet sich weiter unten "
                    "und kann weiterhin ergänzt werden.",
                )

            # Neues leeres Eingabefeld für die nächste Antwort erzeugen
            st.session_state["chat_input_version"] += 1

            st.rerun()

# ---------------------------------------------------------------------------
# Dokumentenupload
# ---------------------------------------------------------------------------
with right_col:

    # Im freien Beratungschat keine Dokumente anzeigen.
    if not application_mode_active:
        st.subheader("📄 BAföG-Erstantrag")

        with st.container(border=True):
            st.markdown("### Antragsassistent starten")

            st.write(
                "Im freien Chat kannst du allgemeine Fragen zur "
                "BAföG-Erstantragstellung stellen."
            )

            st.write(
                "Starte den Antragsassistenten, um Nachweise hochzuladen, "
                "Angaben automatisch auslesen zu lassen und Formblatt 1 "
                "vorzubereiten."
            )

            st.button(
                "BAföG-Erstantrag vorbereiten",
                type="primary",
                use_container_width=True,
                key="start_application_right",
                on_click=start_application_callback,
            )

            # st.caption(
            #     "Nach dem Start erscheint hier der Bereich zum Hochladen "
            #     "der Studienbescheinigung und weiterer Nachweise."
            # )

    # Uploadbereich nur im Antragsmodus anzeigen.
    else:
        st.subheader("📤 Nachweise hochladen")

        st.markdown("**Erforderlich zu Beginn**")

        st.write(
            "Studienbescheinigung nach § 9 BAföG "
            "oder Formblatt 02"
        )

        # st.markdown(
        #     "**Optional zur automatischen Übernahme "
        #     "weiterer Angaben**"
        # )
        #
        # st.write(
        #     "Personalausweis/Reisepass, Lebenslauf, "
        #     "Kranken- und Pflegeversicherungsbescheinigung, "
        #     "Wohnungsnachweis, Einkommensnachweis "
        #     "oder Leistungsnachweis"
        # )

        # st.caption(
        #     "Du kannst optionale Dokumente freiwillig hochladen. "
        #     "Alternativ fragt der Assistent fehlende Angaben später ab. "
        #     "Nutze für Tests möglichst synthetische oder "
        #     "anonymisierte Dokumente."
        # )

        uploader_version = st.session_state[
            "uploader_version"
        ]

        uploaded_files = st.file_uploader(
            "PDF- oder Bilddateien auswählen",
            type=[
                "pdf",
                "png",
                "jpg",
                "jpeg",
                "webp",
            ],
            accept_multiple_files=True,
            key=f"application_document_uploader_{uploader_version}",
        )
        remove_documents_clicked = st.button(
            "Alle Nachweise und erkannten Daten entfernen",
            use_container_width=True,
            key="remove_all_application_documents",
        )

        if remove_documents_clicked:
            # Alten Antragsdialog ebenfalls entfernen,
            # damit keine Fragen aus dem alten Fall stehen bleiben.
            st.session_state["chat_history"] = []

            reset_application()

            append_chat(
                "assistant",
                (
                    "Alle hochgeladenen Nachweise und daraus erkannten Angaben "
                    "wurden entfernt.\n\n"
                    "Bitte lade zuerst deine Studienbescheinigung nach § 9 BAföG "
                    "oder Formblatt 02 hoch. Weitere Dokumente kannst du "
                    "optional gleichzeitig hinzufügen."
                ),
            )

            st.rerun()
        if (
            uploaded_files
            and process_uploaded_files(uploaded_files)
        ):
            st.rerun()

        registry = st.session_state[
            "document_registry"
        ]

        uploaded_documents = [
            (document_type, item)
            for document_type, item in registry.items()
            if item.get("uploaded") is True
        ]

        if uploaded_documents:
            with st.expander(
                f"✅ Erkannte Nachweise ({len(uploaded_documents)})",
                expanded=False,
            ):
                try:
                    document_list_container = st.container(
                        height=320,
                        border=False,
                    )
                except TypeError:
                    # Rückwärtskompatibilität mit älteren Streamlit-Versionen.
                    document_list_container = st.container()

                with document_list_container:
                    for document_type, item in uploaded_documents:
                        label = DOCUMENT_LABELS.get(
                            document_type,
                            document_type.replace("_", " ").title(),
                        )

                        filenames_text = ", ".join(
                            item.get("filenames", [])
                        )

                        field_count = len(
                            item.get("extracted_fields", [])
                        )

                        with st.container(border=True):
                            st.markdown(f"**✅ {label}**")

                            if filenames_text:
                                st.caption(filenames_text)

                            st.caption(
                                f"{field_count} Angaben erkannt"
                            )

                            for warning in item.get("warnings", []):
                                st.warning(warning)

# Im freien Beratungsmodus keine Antragsdaten,
# Checkliste oder Formblatt-Vorschau anzeigen.
if not application_mode_active:
    st.stop()

# ---------------------------------------------------------------------------
# Dynamische Checkliste
# ---------------------------------------------------------------------------
st.divider()
st.subheader("✅ Persönliche Nachweis-Checkliste")

checklist = checklist_manager.update_checklist(
    st.session_state["user_profile"],
    st.session_state["case_state"],
    st.session_state["document_registry"],
)

available_items, required_open_items, optional_items = categorize_checklist(
    checklist
)

st.caption(
    f"{len(available_items)} vorhanden · "
    f"{len(required_open_items)} noch erforderlich · "
    f"{len(optional_items)} optional oder zu prüfen"
)

with st.expander(
    f"✅ Bereits vorhanden ({len(available_items)})",
    expanded=False,
):
    render_checklist_items(
        items=available_items,
        icon="✅",
        empty_message="Es wurden noch keine Nachweise erkannt.",
    )

with st.expander(
    f"📌 Noch erforderlich ({len(required_open_items)})",
    expanded=True,
):
    render_checklist_items(
        items=required_open_items,
        icon="📌",
        empty_message="Aktuell fehlen keine als erforderlich erkannten Nachweise.",
    )

with st.expander(
    f"ℹ️ Optional oder zu prüfen ({len(optional_items)})",
    expanded=False,
):
    render_checklist_items(
        items=optional_items,
        icon="ℹ️",
        empty_message=(
            "Aktuell gibt es keine optionalen oder zu prüfenden Unterlagen."
        ),
    )

# ---------------------------------------------------------------------------
# Kontrollierbare Formblatt-Vorschau nach Kategorien
# ---------------------------------------------------------------------------
st.divider()
st.subheader("🧾 Vorschau der unterstützten Formblatt-1-Felder")

draft = form_manager.build_draft(
    user_profile=st.session_state["user_profile"],
    case_state=st.session_state["case_state"],
    career_entries=st.session_state["career_entries"],
    career_row_count=st.session_state.get(
        "career_row_count",
        1,
    ),
    manual_values=st.session_state["manual_form_values"],
)

progress = form_manager.calculate_progress(draft)

st.progress(progress["percentage"] / 100)
st.caption(
    f"{progress['filled']} von {progress['total']} unterstützten Feldern "
    f"vorbereitet ({progress['percentage']} %). Offene Pflichtfelder: "
    f"{progress['required_open']}."
)

if st.session_state["data_conflicts"]:
    with st.expander("⚠️ Erkannte Datenkonflikte prüfen"):
        for conflict in st.session_state["data_conflicts"][-10:]:
            st.warning(
                f"{conflict['field']}: '{conflict['old_value']}' "
                f"({conflict['old_source']}) vs. '{conflict['new_value']}' "
                f"({conflict['new_source']})"
            )

render_categorized_form_preview(draft)

# Nach Änderungen den aktuellen Fortschritt erneut berechnen.
current_draft = form_manager.build_draft(
    user_profile=st.session_state["user_profile"],
    case_state=st.session_state["case_state"],
    career_entries=st.session_state["career_entries"],
    career_row_count=st.session_state.get(
        "career_row_count",
        1,
    ),
    manual_values=st.session_state["manual_form_values"],
)
current_progress = form_manager.calculate_progress(current_draft)

st.divider()
st.markdown("### Abschließende Prüfung")

if current_progress["required_open"] > 0:
    st.error(
        f"Der Antrag ist noch nicht vollständig. Es fehlen "
        f"{current_progress['required_open']} unterstützte Pflichtfelder. "
        "Öffne die rot markierten Kategorien und ergänze die Angaben."
    )
else:
    st.success(
        "Alle unterstützten Pflichtfelder sind vollständig. "
        "Du kannst die Angaben jetzt bestätigen und die PDF freigeben."
    )

confirm_clicked = st.button(
    "Alle Angaben bestätigen und PDF freigeben",
    type="primary",
    use_container_width=True,
    disabled=(
        current_progress["required_open"] > 0
        or bool(st.session_state.get("editing_section"))
    ),
)

if confirm_clicked:
    st.session_state["form_saved"] = True
    st.session_state["assistant_mode"] = "confirmed"

    append_chat(
        "assistant",
        (
            "Alle unterstützten Pflichtangaben wurden kontrolliert und "
            "bestätigt. Formblatt 1 kann jetzt als PDF vorausgefüllt werden."
        ),
    )

    st.success("Angaben wurden bestätigt.")
    st.rerun()

# ---------------------------------------------------------------------------
# PDF-Erstellung
# ---------------------------------------------------------------------------
confirmed_draft = form_manager.build_draft(
    user_profile=st.session_state["user_profile"],
    case_state=st.session_state["case_state"],
    career_entries=st.session_state["career_entries"],
    career_row_count=st.session_state.get(
        "career_row_count",
        1,
    ),
    manual_values=st.session_state["manual_form_values"],

)

if st.session_state["form_saved"]:
    try:
        pdf_bytes = pdf_filler.fill(FORM_TEMPLATE, confirmed_draft)

        st.download_button(
            "Formblatt 1 als PDF vorausfüllen",
            data=pdf_bytes,
            file_name="Formblatt_1_vorausgefuellt.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        st.warning(
            "Die PDF-Vorlage muss vor der Einreichung vollständig kontrolliert "
            "werden. Nicht unterstützte oder offene Felder bleiben leer. Die "
            "bereitgestellte Vorlage enthält bei der Vermögensfrage möglicherweise "
            "ältere Grenzbeträge; deshalb wird dieses Kontrollkästchen nicht "
            "automatisch gesetzt."
        )

    except Exception as exc:  # noqa: BLE001
        st.error(f"PDF konnte nicht erstellt werden: {exc}")
else:
    st.info(
        "Aktiviere zuerst „Bearbeiten“ und speichere die kontrollierten "
        "Angaben. Danach wird die PDF-Schaltfläche freigeschaltet."
    )