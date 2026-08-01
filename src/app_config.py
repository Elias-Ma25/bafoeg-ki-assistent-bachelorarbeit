from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# Lädt die lokale .env-Datei.
load_dotenv()


# ---------------------------------------------------------------------------
# Zugangsschutz
# ---------------------------------------------------------------------------
def get_secret(name: str, default: str = "") -> str:
    """Liest einen Wert aus .env/Umgebungsvariablen oder Streamlit Secrets."""

    environment_value = os.getenv(name, "").strip()

    if environment_value:
        return environment_value

    try:
        return str(
            st.secrets.get(name, default)
        ).strip()
    except Exception:
        return default


APP_ACCESS_PASSWORD = get_secret(
    "APP_ACCESS_PASSWORD"
)


ADMIN_PASSWORD = get_secret(
    "ADMIN_PASSWORD"
)
# ---------------------------------------------------------------------------
# OpenAI und RAG
# ---------------------------------------------------------------------------
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1",
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
)

KNOWLEDGE_FOLDER = os.getenv(
    "KNOWLEDGE_FOLDER",
    "data/knowledge",
)

VECTORSTORE_DIR = os.getenv(
    "VECTORSTORE_DIR",
    "chroma_db",
)

# ---------------------------------------------------------------------------
# PDF-Vorlage
# ---------------------------------------------------------------------------
FORM_TEMPLATE = Path(
    os.getenv(
        "FORMBLATT_1_TEMPLATE",
        "formblatt_1.pdf",
    )
)

# ---------------------------------------------------------------------------
# Unterstützte Profildaten
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Unterstützte Dokumenttypen
# ---------------------------------------------------------------------------
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
    "studienbescheinigung": (
        "Studienbescheinigung"
    ),
    "identitaetsdokument": (
        "Personalausweis oder Reisepass"
    ),
    "vollmacht": (
        "Vollmacht"
    ),
    "lebenslauf": (
        "Lebenslauf"
    ),
    "kranken_pflegeversicherungsnachweis": (
        "Kranken- und Pflegeversicherungsnachweis"
    ),
    "wohnungsnachweis": (
        "Wohnungsnachweis"
    ),
    "einkommensnachweis": (
        "Einkommensnachweis"
    ),
    "vermoegensnachweis": (
        "Vermögensnachweis"
    ),
    "leistungsnachweis": (
        "Leistungsnachweis"
    ),
    "unbekannt": (
        "Unbekanntes Dokument"
    ),
}