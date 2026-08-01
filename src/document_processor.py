from __future__ import annotations
from datetime import date
import base64
import json
import re
from io import BytesIO
from typing import Any

from pypdf import PdfReader

SUPPORTED_DOCUMENT_TYPES = {
    "studienbescheinigung",
    "identitaetsdokument",
    "lebenslauf",
    "vollmacht",
    "kranken_pflegeversicherungsnachweis",
    "wohnungsnachweis",
    "einkommensnachweis",
    "vermoegensnachweis",
    "leistungsnachweis",
    "unbekannt",
}

PROFILE_FIELDS = {
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
    "telefon",
    "email",
    "ausbildung_strasse",
    "ausbildung_hausnummer",
    "ausbildung_adresszusatz",
    "ausbildung_land",
    "ausbildung_plz",
    "ausbildung_ort",
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

CASE_FIELDS = {
    "vollzeitausbildung",
    "krankenversicherung",
    "pflegeversicherung_selbst_beitragspflichtig",
    "eigenes_einkommen",
    "wohnsituation",
    "wohnraum_eigentum_eltern",
    "familienstand",
    "kinder",
}
CASE_FIELD_ALLOWED_VALUES = {
    "vollzeitausbildung": {
        "ja",
        "nein",
    },
    "krankenversicherung": {
        "familienversichert",
        "studentisch_gesetzlich",
        "freiwillig_gesetzlich",
        "privat",
        "anders",
    },
    "pflegeversicherung_selbst_beitragspflichtig": {
        "ja",
        "nein",
    },
    "eigenes_einkommen": {
        "ja",
        "nein",
    },
    "wohnsituation": {
        "bei_eltern",
        "nicht_bei_eltern",
    },
    "wohnraum_eigentum_eltern": {
        "ja",
        "nein",
        "nicht_relevant",
    },
    "familienstand": {
        "ledig",
        "verheiratet",
        "dauernd_getrennt",
        "verwitwet",
        "geschieden",
    },
    "kinder": {
        "ja",
        "nein",
    },
}

def normalize_family_status_value(
    value: str,
) -> str:
    """Vereinheitlicht Familienstandsangaben aus Dokumenten."""

    normalized = str(value or "").strip().lower()

    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)

    aliases = {
        "ledig": "ledig",
        "unverheiratet": "ledig",
        "nicht verheiratet": "ledig",

        "verheiratet": "verheiratet",
        "eingetragene lebenspartnerschaft": "verheiratet",
        "verheiratet / eingetragene lebenspartnerschaft": (
            "verheiratet"
        ),

        "dauernd getrennt": "dauernd_getrennt",
        "dauernd getrennt lebend": "dauernd_getrennt",
        "getrennt lebend": "dauernd_getrennt",

        "verwitwet": "verwitwet",

        "geschieden": "geschieden",
        "lebenspartnerschaft aufgehoben": "geschieden",
        "aufgehoben": "geschieden",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def normalize_children_value(
    value: str,
) -> str:
    """Vereinheitlicht Angaben zu eigenen Kindern."""

    normalized = str(value or "").strip().lower()

    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)

    negative_values = {
        "nein",
        "keine",
        "kein kind",
        "keine kinder",
        "keine eigenen kinder",
        "kinderlos",
        "nicht vorhanden",
    }

    positive_values = {
        "ja",
        "eigene kinder",
        "kinder vorhanden",
        "ein kind",
        "1 kind",
    }

    if normalized in negative_values:
        return "nein"

    if normalized in positive_values:
        return "ja"

    if re.search(
        r"\b\d+\s+kinder?\b",
        normalized,
    ):
        return "ja"

    return normalized

def deterministic_personal_case_fallback(
    text: str,
) -> dict[str, dict[str, str]]:
    """Erkennt eindeutige Angaben zu Familienstand und Kindern."""

    text = str(text or "")
    updates: dict[str, dict[str, str]] = {}

    family_match = re.search(
        r"Familienstand\s*[:\-]?\s*"
        r"(Ledig|Verheiratet|Dauernd getrennt(?: lebend)?|"
        r"Verwitwet|Geschieden)",
        text,
        flags=re.IGNORECASE,
    )

    if family_match:
        family_status = normalize_family_status_value(
            family_match.group(1)
        )

        if family_status in CASE_FIELD_ALLOWED_VALUES["familienstand"]:
            updates["familienstand"] = {
                "value": family_status,
                "confidence": "high",
            }

    children_match = re.search(
        r"Eigene\s+Kinder\s*[:\-]?\s*([^\n\r]+)",
        text,
        flags=re.IGNORECASE,
    )

    if children_match:
        children = normalize_children_value(
            children_match.group(1)
        )

        if children in CASE_FIELD_ALLOWED_VALUES["kinder"]:
            updates["kinder"] = {
                "value": children,
                "confidence": "high",
            }

    return updates

def normalize_insurance_value(value: str) -> str:
    """
    Vereinheitlicht unterschiedliche Formulierungen
    auf die intern erlaubten Versicherungswerte.
    """
    normalized = str(value or "").strip().lower()

    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)

    aliases = {
        "familienversichert": "familienversichert",
        "gesetzlich familienversichert": "familienversichert",
        "familienversicherung": "familienversichert",
        "über die eltern versichert": "familienversichert",
        "ueber die eltern versichert": "familienversichert",

        "studentisch gesetzlich": "studentisch_gesetzlich",
        "gesetzlich studentisch": "studentisch_gesetzlich",
        "studentisch versichert": "studentisch_gesetzlich",
        "studentische krankenversicherung": "studentisch_gesetzlich",
        "krankenversicherung der studenten": "studentisch_gesetzlich",
        "kvds": "studentisch_gesetzlich",
        "studentisch_gesetzlich": "studentisch_gesetzlich",

        "freiwillig versichert": "freiwillig_gesetzlich",
        "freiwillig gesetzlich": "freiwillig_gesetzlich",
        "freiwillige krankenversicherung": "freiwillig_gesetzlich",
        "freiwillig_gesetzlich": "freiwillig_gesetzlich",

        "privat": "privat",
        "privat versichert": "privat",
        "private krankenversicherung": "privat",

        "anders": "anders",
        "sonstige": "anders",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def normalize_case_updates(
        raw_updates: Any
) -> dict[str, dict[str, str]]:
    """
    Normalisiert und validiert die aus Dokumenten
    erkannten Fallinformationen.
    """
    if not isinstance(raw_updates, dict):
        return {}

    normalized_updates: dict[str, dict[str, str]] = {}

    for field_name, payload in raw_updates.items():
        field_name = str(field_name).strip()

        if field_name not in CASE_FIELDS:
            continue

        if isinstance(payload, dict):
            value = str(
                payload.get("value", "")
            ).strip()

            confidence = str(
                payload.get("confidence", "medium")
            ).strip().lower()
        else:
            value = str(payload).strip()
            confidence = "medium"

        if field_name == "krankenversicherung":
            value = normalize_insurance_value(value)

        elif field_name == "familienstand":
            value = normalize_family_status_value(value)

        elif field_name == "kinder":
            value = normalize_children_value(value)

        else:
            value = value.strip().lower()


        if confidence not in {
            "high",
            "medium",
            "low",
        }:
            confidence = "medium"

        allowed_values = CASE_FIELD_ALLOWED_VALUES.get(
            field_name,
            set(),
        )

        if value not in allowed_values:
            continue

        normalized_updates[field_name] = {
            "value": value,
            "confidence": confidence,
        }

    return normalized_updates


PROFILE_FIELDS_BY_DOCUMENT_TYPE = {
    "studienbescheinigung": {
        "vorname",
        "nachname",
        "geburtsdatum",
        "geburtsort",
        "matrikelnummer",
        "hochschule",
        "ausbildungsort",
        "studiengang",
        "abschlussziel",
        "hochschulsemester",
        "fachsemester",
        "regelstudienzeit",
    },

    "lebenslauf": {
        "vorname",
        "nachname",
        "geburtsdatum",
        "anschrift_strasse",
        "anschrift_hausnummer",
        "anschrift_adresszusatz",
        "anschrift_land",
        "anschrift_plz",
        "anschrift_ort",
        "telefon",
        "email",
        "hochschule",
        "studiengang",
        "abschlussziel",
    },
}

def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Extrahiert eingebetteten Text aus einer PDF-Datei.

    Bei gescannten PDFs kann das Ergebnis leer sein; dann wird der multimodale
    Fallback verwendet.
    """
    reader = PdfReader(BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages).strip()

def detect_document_type_locally(
        filename: str,
        extracted_text: str
) -> str:
    """
    Erkennt besonders eindeutige Dokumenttypen anhand
    des Dateinamens und des extrahierten Textes.

    Das Ergebnis verwendet exakt die internen Dokumenttyp-Namen.
    """
    filename_lower = str(filename or "").lower()
    text_lower = str(extracted_text or "").lower()

    combined_text = f"{filename_lower}\n{text_lower}"

    # Kranken- und Pflegeversicherungsnachweis
    insurance_filename_markers = [
        "krankenversicherungsnachweis",
        "krankenversicherung",
        "pflegeversicherungsnachweis",
    ]

    insurance_text_markers = [
        "krankenversicherung",
        "pflegeversicherung",
        "amt für ausbildungsförderung",
        "amt fuer ausbildungsfoerderung",
        "§13 a bafög",
        "§ 13 a bafög",
        "§13a bafög",
    ]

    filename_indicates_insurance = any(
        marker in filename_lower
        for marker in insurance_filename_markers
    )

    text_indicates_insurance = (
        (
            "krankenversicherung" in text_lower
            or "pflegeversicherung" in text_lower
        )
        and any(
            marker in text_lower
            for marker in insurance_text_markers
        )
    )

    if filename_indicates_insurance or text_indicates_insurance:
        return "kranken_pflegeversicherungsnachweis"

    # Studienbescheinigung
    if (
        "studienbescheinigung" in filename_lower
        or "immatrikulationsbescheinigung" in filename_lower
        or (
            "fachsemester" in text_lower
            and "matrikel" in text_lower
            and (
                "immatrikulationsbescheinigung" in text_lower
                or "bescheinigung nach § 9 bafög" in text_lower
            )
        )
    ):
        return "studienbescheinigung"

    # Lebenslauf
    if (
        "lebenslauf" in filename_lower
        or (
            "berufserfahrung" in text_lower
            and "ausbildung" in text_lower
        )
    ):
        return "lebenslauf"

    return "unbekannt"

def _strip_json_fence(raw: str) -> str:
    raw = str(raw or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```")
        raw = raw.removesuffix("```").strip()
    return raw


def _normalize_field_updates(raw_updates: Any, allowed_fields: set[str]) -> dict[str, dict[str, str]]:
    if not isinstance(raw_updates, dict):
        return {}

    normalized: dict[str, dict[str, str]] = {}
    for field_name, payload in raw_updates.items():
        field_name = str(field_name).strip()
        if field_name not in allowed_fields:
            continue

        if isinstance(payload, dict):
            value = str(payload.get("value", "")).strip()
            confidence = str(payload.get("confidence", "medium")).strip().lower()
        else:
            value = str(payload).strip()
            confidence = "medium"

        if not value:
            continue
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"

        normalized[field_name] = {"value": value, "confidence": confidence}
    return normalized


def normalize_document_result(
        result: dict[str, Any],
        filename: str
) -> dict[str, Any]:
    """Normalisiert das vom Sprachmodell gelieferte Dokumentergebnis."""

    document_type = str(
        result.get("document_type", "unbekannt")
    ).strip()

    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        document_type = "unbekannt"

    confidence = str(
        result.get("confidence", "medium")
    ).strip().lower()

    if confidence not in {
        "high",
        "medium",
        "low",
    }:
        confidence = "medium"

    career_entries = result.get(
        "career_entries",
        [],
    )

    if not isinstance(career_entries, list):
        career_entries = []

    normalized_entries: list[dict[str, str]] = []

    for entry in career_entries[:16]:
        if not isinstance(entry, dict):
            continue

        normalized_entries.append(
            {
                "von": str(
                    entry.get("von", "")
                ).strip(),
                "bis": str(
                    entry.get("bis", "")
                ).strip(),
                "name_ort": str(
                    entry.get("name_ort", "")
                ).strip(),
                "art": str(
                    entry.get("art", "")
                ).strip(),
                "abschluss_leistung": str(
                    entry.get(
                        "abschluss_leistung",
                        ""
                    )
                ).strip(),
            }
        )

    warnings = result.get(
        "warnings",
        [],
    )

    if not isinstance(warnings, list):
        warnings = []

    allowed_profile_fields = (
        PROFILE_FIELDS_BY_DOCUMENT_TYPE.get(
            document_type,
            PROFILE_FIELDS,
        )
    )

    profile_updates = _normalize_field_updates(
        result.get("profile_updates"),
        allowed_profile_fields,
    )

    case_updates = normalize_case_updates(
        result.get("case_updates")
    )

    return {
        "document_type": document_type,
        "confidence": confidence,
        "filename": filename,
        "summary": str(
            result.get("summary", "")
        ).strip(),
        "profile_updates": profile_updates,
        "case_updates": case_updates,
        "career_entries": normalized_entries,
        "warnings": [
            str(item).strip()
            for item in warnings
            if str(item).strip()
        ],
    }


def deterministic_study_fallback(text: str) -> dict[str, dict[str, str]]:
    """Einfache Regex-Rückfallebene für typische Studienbescheinigungen."""
    patterns = {
        "matrikelnummer": [r"Matrikel(?:nummer|-Nr\.?| Nr\.?)\s*[:\-]?\s*([A-Za-z0-9]+)"],
        "geburtsdatum": [r"geboren\s+am\s+(\d{2}\.\d{2}\.\d{4})", r"Geburtsdatum\s*[:\-]?\s*(\d{2}\.\d{2}\.\d{4})"],
        "geburtsort": [r"geboren\s+in\s+([^\n\r]+)", r"Geburtsort\s*[:\-]?\s*([^\n\r]+)"],
        "studiengang": [r"Studiengang\s*[:\-]?\s*([^\n\r]+)", r"im Studiengang\s+([^\n\r]+)"],
        "abschlussziel": [r"Abschlussziel\s*[:\-]?\s*([^\n\r]+)", r"mit dem Abschlussziel\s+([^\n\r]+)"],
        "hochschulsemester": [r"Hochschulsemester\s*[:\-]?\s*(\d+)"],
        "fachsemester": [r"Fachsemester\s*[:\-]?\s*(\d+)"],
        "regelstudienzeit": [r"Regelstudienzeit\s*[:\-]?\s*(\d+)"],
    }

    updates: dict[str, dict[str, str]] = {}
    for field, field_patterns in patterns.items():
        for pattern in field_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                updates[field] = {"value": match.group(1).strip(), "confidence": "medium"}
                break
    return updates

def deterministic_insurance_fallback(
        text: str
) -> dict[str, dict[str, str]]:
    """
    Erkennt die Versicherungsart aus dem lokal extrahierten PDF-Text.

    Unterstützt insbesondere die BAföG-Bescheinigung der Krankenkasse,
    bei der das Kontrollzeichen durch pypdf teilweise hinter dem Text
    ausgegeben wird.
    """
    normalized_text = str(text or "").lower()

    normalized_text = normalized_text.replace(
        "\u00ad",
        "",
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        normalized_text,
    )

    insurance_value = ""

    student_patterns = [
        r"\bstudentisch versichert\b",
        r"\bstudentisch gesetzlich versichert\b",
        r"\bgesetzlich studentisch versichert\b",
        r"\bstudentische krankenversicherung\b",
        r"\bkrankenversicherung der studenten\b",
        r"\bkrankenversicherung für studenten\b",
        r"\bkvds\b",

        # Tatsächliche Reihenfolge im extrahierten DAK-Dokument:
        # nach § 5 ... SGB V Krankenversicherung....X
        (
            r"nach\s*§\s*5\s*abs\.?\s*1\s*nr\.?\s*9"
            r"(?:\s*oder\s*10)?\s*sgb\s*v"
            r".{0,100}"
            r"krankenversicherung"
            r"[.\s:]*x"
        ),

        # Alternative Textreihenfolge bei anderen PDF-Generatoren:
        # X Krankenversicherung ... nach § 5 ...
        (
            r"x.{0,60}"
            r"krankenversicherung"
            r".{0,120}"
            r"§\s*5\s*abs\.?\s*1\s*nr\.?\s*9"
            r"(?:\s*oder\s*10)?\s*sgb\s*v"
        ),
    ]

    family_patterns = [
        r"\bfamilienversichert\b",
        r"\bgesetzlich familienversichert\b",
        r"\bfamilienversicherung\b",
    ]

    voluntary_patterns = [
        r"\bfreiwillig versichert\b",
        r"\bfreiwillig gesetzlich versichert\b",
        r"\bfreiwillige krankenversicherung\b",

        # „als freiwilliges Mitglied“ nur übernehmen,
        # wenn unmittelbar ein Kontrollzeichen zugeordnet ist.
        r"x.{0,40}als\s+freiwilliges\s+mitglied\b",
        r"als\s+freiwilliges\s+mitglied.{0,20}x\b",
    ]

    private_patterns = [
        r"\bprivat versichert\b",
        r"\bprivate krankenversicherung\b",
        r"\bprivate versicherung\b",
    ]

    if any(
            re.search(pattern, normalized_text)
            for pattern in student_patterns
    ):
        insurance_value = "studentisch_gesetzlich"

    elif any(
            re.search(pattern, normalized_text)
            for pattern in family_patterns
    ):
        insurance_value = "familienversichert"

    elif any(
            re.search(pattern, normalized_text)
            for pattern in voluntary_patterns
    ):
        insurance_value = "freiwillig_gesetzlich"

    elif any(
            re.search(pattern, normalized_text)
            for pattern in private_patterns
    ):
        insurance_value = "privat"

    if not insurance_value:
        return {}

    return {
        "krankenversicherung": {
            "value": insurance_value,
            "confidence": "high",
        },
        "pflegeversicherung_selbst_beitragspflichtig": {
            "value": (
                "nein"
                if insurance_value == "familienversichert"
                else "ja"
            ),
            "confidence": "medium",
        },
    }

def is_insurance_checkbox_document(
        filename: str,
        extracted_text: str
) -> bool:
    """
    Erkennt typische Kranken- und Pflegeversicherungsbescheinigungen.

    Diese Dokumente enthalten häufig Kontrollkästchen.
    Deshalb sollen sie multimodal und nicht nur als Text analysiert werden.
    """
    combined_text = (
        f"{filename} {extracted_text}"
    ).lower()

    insurance_markers = [
        "krankenversicherungsnachweis",
        "krankenversicherung",
        "pflegeversicherung",
        "amt für ausbildungsförderung",
        "§13 a bafög",
        "§ 13 a bafög",
    ]

    return any(
        marker in combined_text
        for marker in insurance_markers
    )

class DocumentProcessor:
    """Klassifiziert Nachweise und extrahiert strukturierte Formblatt-Daten.

    Text-PDFs werden lokal mit pypdf gelesen und anschließend strukturiert vom LLM
    interpretiert. Bilder und gescannte PDFs werden als multimodale Eingabe an die
    Responses API übergeben.
    """

    def __init__(self, client, model: str = "gpt-4.1") -> None:
        self.client = client
        self.model = model

    @staticmethod
    def build_extraction_prompt(filename: str) -> str:
        current_date = date.today().strftime("%d.%m.%Y")
        return f"""
        
Regeln für warnings:
- Erzeuge nur Warnungen bei echten Problemen mit dem Dokument.
- Eine Studienbescheinigung muss keine früheren schulischen oder
  beruflichen Ausbildungsstationen enthalten.
- Der Werdegang wird aus dem Lebenslauf oder aus Nutzereingaben ermittelt.
- Die erstmalige Einschreibung ist eine Information und keine Warnung.
- Erzeuge keine Warnung über fehlende vorherige Ausbildungsstationen.        
     
Heutiges Datum: {current_date}
Zeitliche Regeln:
- Bezeichne ein Datum oder einen Zeitraum nur dann als zukünftig,
  wenn sein Beginn nach dem heutigen Datum liegt.
- Ein Zeitraum, dessen Beginn vor dem heutigen Datum liegt,
  darf nicht als zukünftig bezeichnet werden.
- Beispiel: Wenn heute 25.07.2026 ist, liegt 09/2024 nicht in der Zukunft.
- Erzeuge keine Warnung nur aufgrund eines vergangenen Praxissemesters.

Du analysierst ein Dokument für einen deutschen BAföG-Erstantrag.
Dateiname: {filename}

Mögliche Dokumenttypen:
- studienbescheinigung
- identitaetsdokument (deutscher Personalausweis oder Reisepass)
- lebenslauf
- kranken_pflegeversicherungsnachweis
- wohnungsnachweis
- einkommensnachweis
- vermoegensnachweis
- leistungsnachweis
- unbekannt

Extrahiere ausschließlich Angaben, die im Dokument tatsächlich sichtbar oder eindeutig enthalten sind.
Erfinde nichts. Bei Unsicherheit lasse das Feld weg oder setze confidence = low.

Zulässige Profilfelder:
{sorted(PROFILE_FIELDS)}

Zulässige Fallfelder:
{sorted(CASE_FIELDS)}

Normalisierung:
- geburtsdatum: TT.MM.JJJJ
- geschlecht: weiblich | maennlich | divers | ohne_angabe
- staatsangehoerigkeit: bei deutschem Dokument "deutsch"
- vollzeitausbildung: ja | nein
- krankenversicherung: familienversichert | studentisch_gesetzlich | freiwillig_gesetzlich | privat | anders
- pflegeversicherung_selbst_beitragspflichtig: ja | nein
- eigenes_einkommen: ja | nein, aber nur wenn das Dokument dies wirklich belegt
- wohnsituation: bei_eltern | nicht_bei_eltern, nur wenn aus dem Dokument eindeutig
- wohnraum_eigentum_eltern: ja | nein, nur wenn eindeutig
- Bei Personalausweis/Reisepass oder Lebenslauf gehören Adressdaten grundsätzlich in anschrift_*.
- Bei Wohnungsgeberbescheinigung, Meldebescheinigung oder Mietvertrag gehören die erkannte Ausbildungswohnung in ausbildung_*.
- Eine Versicherungsbescheinigung kann krankenversicherung und pflegeversicherung_selbst_beitragspflichtig liefern.
Regeln für Kranken- und Pflegeversicherungsnachweise:

- Diese Dokumente können Kontrollkästchen enthalten.
- Berücksichtige ausschließlich tatsächlich angekreuzte oder markierte Optionen.
- Der bloße sichtbare Text einer nicht angekreuzten Option ist keine Angabe.
- Prüfe die räumliche Zuordnung zwischen Kästchen und Beschriftung.

- Ist das Kästchen bei
  „nach § 5 Abs. 1 Nr. 9 oder 10 SGB V“
  markiert, setze:
  krankenversicherung = studentisch_gesetzlich

- Ist das Kästchen bei
  „als freiwilliges Mitglied“
  markiert, setze:
  krankenversicherung = freiwillig_gesetzlich

- Ist das Kästchen bei der Pflegeversicherung markiert, setze:
  pflegeversicherung_selbst_beitragspflichtig = ja

- Verwechsle eine nicht markierte Beschriftung
  „als freiwilliges Mitglied“
  niemals mit einer tatsächlich freiwilligen Versicherung.

- Wenn nicht sicher erkennbar ist, welches Kästchen markiert wurde,
  lasse das entsprechende Feld weg.

- Erfinde keine Versicherungsart.

- Ein Einkommensnachweis darf eigenes_einkommen = ja setzen, aber keine zukünftigen Gesamtsummen erfinden.

- Bei einem Lebenslauf darfst du Fachsemester, Hochschulsemester,
  Regelstudienzeit und Matrikelnummer niemals aus Zeitangaben ableiten.
- Gib diese Felder bei einem Lebenslauf nicht in profile_updates aus.
- "Seit 10/2022 studiert" beschreibt einen Zeitraum, aber kein ausdrücklich
  genanntes Fachsemester.
Bei einem Lebenslauf extrahiere zusätzlich bis zu 16 chronologische Stationen.
Jede Station enthält: von, bis, name_ort, art, abschluss_leistung.
Weise in warnings auf erkennbare zeitliche Lücken oder unklare Angaben hin.

Gib ausschließlich JSON zurück:
{{
  "document_type": "...",
  "confidence": "high|medium|low",
  "summary": "kurze Beschreibung",
  "profile_updates": {{
    "feld": {{"value": "...", "confidence": "high|medium|low"}}
  }},
  "case_updates": {{
    "feld": {{"value": "...", "confidence": "high|medium|low"}}
  }},
  "career_entries": [
    {{"von": "MM/JJJJ", "bis": "MM/JJJJ oder offen", "name_ort": "...", "art": "...", "abschluss_leistung": "..."}}
  ],
  "warnings": ["..."]
}}
""".strip()

    def _extract_from_text(self, filename: str, text: str) -> dict[str, Any]:
        prompt = self.build_extraction_prompt(filename)
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du extrahierst strukturierte Daten aus "
                        "BAföG-Nachweisen und antwortest nur als JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nDokumenttext:\n{text[:30000]}",
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=2200,
        )
        return json.loads(_strip_json_fence(completion.choices[0].message.content))

    def _extract_multimodal(
            self,
            filename: str,
            mime_type: str,
            file_bytes: bytes
    ) -> dict[str, Any]:
        """
        Analysiert PDFs und Bilder multimodal.

        PDFs werden als Base64-Data-URL übergeben, damit neben dem
        extrahierten Text auch sichtbare Elemente wie Kontrollkästchen
        ausgewertet werden können.
        """
        prompt = self.build_extraction_prompt(filename)

        encoded = base64.b64encode(
            file_bytes
        ).decode("ascii")

        is_pdf = (
                mime_type == "application/pdf"
                or filename.lower().endswith(".pdf")
        )

        if is_pdf:
            pdf_data_url = (
                f"data:application/pdf;base64,{encoded}"
            )

            content = [
                {
                    "type": "input_file",
                    "filename": filename,
                    "file_data": pdf_data_url,
                    "detail": "high",
                },
                {
                    "type": "input_text",
                    "text": prompt,
                },
            ]

        else:
            effective_mime_type = (
                mime_type
                if mime_type.startswith("image/")
                else "image/jpeg"
            )

            image_data_url = (
                f"data:{effective_mime_type};base64,{encoded}"
            )

            content = [
                {
                    "type": "input_image",
                    "image_url": image_data_url,
                    "detail": "high",
                },
                {
                    "type": "input_text",
                    "text": prompt,
                },
            ]

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_output_tokens=4000,
        )

        raw_output = str(
            response.output_text or ""
        ).strip()

        if not raw_output:
            raise ValueError(
                "Die multimodale Dokumentanalyse hat keine Antwort geliefert."
            )

        return json.loads(
            _strip_json_fence(raw_output)
        )

    def process(self, filename: str, mime_type: str, file_bytes: bytes) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("Kein OpenAI API-Key gefunden.")
        if not file_bytes:
            raise ValueError("Die Datei ist leer.")

        extracted_text = ""
        if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                extracted_text = extract_text_from_pdf_bytes(file_bytes)
            except Exception:  # noqa: BLE001 - Multimodaler Fallback folgt.
                extracted_text = ""

        local_document_type = detect_document_type_locally(
            filename=filename,
            extracted_text=extracted_text,
        )

        insurance_checkbox_document = (
            is_insurance_checkbox_document(
                filename=filename,
                extracted_text=extracted_text,
            )
        )

        # Versicherungsbescheinigungen enthalten Kontrollkästchen.
        # Die visuelle PDF-Analyse kann erkennen, welches Kästchen markiert ist.
        if insurance_checkbox_document:
            raw_result = self._extract_multimodal(
                filename=filename,
                mime_type=mime_type,
                file_bytes=file_bytes,
            )

        elif len(extracted_text) >= 80:
            raw_result = self._extract_from_text(
                filename=filename,
                text=extracted_text,
            )

        else:
            raw_result = self._extract_multimodal(
                filename=filename,
                mime_type=mime_type,
                file_bytes=file_bytes,
            )

        result = normalize_document_result(
            raw_result,
            filename
        )

        # Eine eindeutige lokale Klassifikation hat Vorrang
        # vor einer unsicheren LLM-Klassifikation.
        if local_document_type != "unbekannt":
            result["document_type"] = local_document_type
            result["confidence"] = "high"

        result["extracted_text"] = extracted_text

        # Eindeutige Versicherungsart direkt aus dem Dokumenttext erkennen.
        if (
                (
                        result["document_type"]
                        == "kranken_pflegeversicherungsnachweis"
                        or local_document_type
                        == "kranken_pflegeversicherungsnachweis"
                )
                and extracted_text
        ):
            insurance_fallback = (
                deterministic_insurance_fallback(
                    extracted_text
                )
            )

            for field_name, payload in insurance_fallback.items():
                # Die eindeutige lokale Erkennung hat Vorrang
                # vor einer fehlenden oder falschen LLM-Auslegung.
                result["case_updates"][field_name] = payload

        # Ergänzende lokale Rückfallebene für Studienbescheinigungen.
        if (
                result["document_type"]
                == "studienbescheinigung"
                and extracted_text
        ):
            fallback = deterministic_study_fallback(
                extracted_text
            )

            for field_name, payload in fallback.items():
                result["profile_updates"].setdefault(
                    field_name,
                    payload,
                )

        return result
