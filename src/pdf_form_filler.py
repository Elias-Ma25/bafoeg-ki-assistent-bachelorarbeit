from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Any
import re
from datetime import date,datetime
from pypdf import PdfReader, PdfWriter
from pypdf.generic import BooleanObject, NameObject


class PdfFormFiller:
    """Überträgt bestätigte Vorschauwerte in ausgewählte AcroForm-Felder."""

    INSURANCE_PDF_STATES = {
        "gesetzlich familienversichert": "/gesetzlich familienversichert",
        "studentisch gesetzlich versichert": "/studentisch familienversichert",
        "freiwillig gesetzlich versichert": "/freiwillig gesetzlich versichert",
        "privat versichert": "/privat versichert",
        "anders versichert": "/anders versichert",
    }

    ASSET_PDF_FIELD_UNDER_30 = (
        "unter 30 Jahre alt und Vermögen "
        "insgesamt unter 10.000 Euro"
    )

    ASSET_PDF_FIELD_FROM_30 = (
        "über 30 Jahre alt und Vermögen "
        "insgesamt unter 30.000 Euro"
    )

    NOTICE_RECIPIENT_PDF_STATES = {
        "An mich – ständiger Wohnsitz": (
            "/mich (st鋘diger Wohnsitz)"
        ),
        "An mich – Anschrift während der Ausbildung": (
            "/mich (Wohnsitz am Ausbildungsort)"
        ),
        "An meinen ersten Elternteil": (
            "/meinen ersten Elternteil"
        ),
        "An meinen zweiten Elternteil": (
            "/meinen zweiten Elternteil"
        ),
        "An meine sorgeberechtigte Person": (
            "/meine/-n Sorgeberechtigte/-n"
        ),
        "An eine von mir bevollmächtigte Person": (
            "/die von mir bevollm鋍htigte Person"
        ),
    }

    @staticmethod
    def _parse_birthdate(
            value: str,
    ) -> date | None:
        """Liest das Geburtsdatum aus unterstützten Formaten."""

        value = str(value or "").strip()

        if not value:
            return None

        formats = (
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
        )

        for date_format in formats:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                ).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _calculate_age(
            birthdate: date,
            reference_date: date | None = None,
    ) -> int:
        """Berechnet das Alter am Tag der PDF-Erstellung."""

        current_date = reference_date or date.today()

        return (
                current_date.year
                - birthdate.year
                - (
                        (current_date.month, current_date.day)
                        < (birthdate.month, birthdate.day)
                )
        )

    def _add_asset_selection(
            self,
            values: dict[str, str],
            draft: dict[str, dict[str, Any]],
    ) -> None:
        """Überträgt die Vermögensantwort in die passende Altersgruppe."""

        asset_answer = str(
            draft.get(
                "vermoegen_unter_grenze",
                {},
            ).get(
                "value",
                "",
            )
        ).strip().lower()

        if asset_answer not in {"ja", "nein"}:
            return

        birthdate_value = str(
            draft.get(
                "geburtsdatum",
                {},
            ).get(
                "value",
                "",
            )
        ).strip()

        birthdate = self._parse_birthdate(
            birthdate_value
        )

        if birthdate is None:
            return

        age = self._calculate_age(
            birthdate
        )

        if age < 30:
            pdf_field = self.ASSET_PDF_FIELD_UNDER_30
        else:
            pdf_field = self.ASSET_PDF_FIELD_FROM_30

        values[pdf_field] = self._button(
            asset_answer
        )

    @staticmethod
    def _button(value: str) -> str:
        value = str(value).strip().lower()
        if value == "ja":
            return "/ja"
        if value == "nein":
            return "/nein"
        return value

    @staticmethod
    def _checkbox(value: str) -> str:
        return "/ja" if str(value).strip().lower() == "ja" else "/Off"

    @staticmethod
    def _family_status(value: str) -> str:
        value = str(value).strip()
        if value and value[0] in "12345":
            return value[0]
        mapping = {
            "ledig": "1",
            "verheiratet": "2",
            "dauernd_getrennt": "3",
            "verwitwet": "4",
            "geschieden": "5",
        }
        return mapping.get(value.lower(), value)

    @staticmethod
    def _month_year_for_pdf(value: str) -> str:
        """Wandelt unterstützte Monatsangaben in MMJJJJ um."""

        value = str(value or "").strip()

        if not value:
            return ""

        supported_formats = (
            "%m.%Y",
            "%m/%Y",
            "%m-%Y",
            "%Y-%m",
        )

        for date_format in supported_formats:
            try:
                parsed_date = datetime.strptime(
                    value,
                    date_format,
                )

                return parsed_date.strftime(
                    "%m%Y"
                )

            except ValueError:
                continue

        digits = re.sub(
            r"\D",
            "",
            value,
        )

        if len(digits) == 6:
            # Bereits MMJJJJ
            if not digits.startswith(("19", "20")):
                return digits

            # JJJJMM in MMJJJJ umwandeln
            return digits[4:6] + digits[0:4]

        raise ValueError(
            "Der Bewilligungszeitraum muss beispielsweise "
            "als 09.2026 angegeben werden."
        )

    @staticmethod
    def _birthdate_for_pdf(value: str) -> str:
        """Wandelt unterstützte Datumsformate in TTMMJJJJ um."""

        value = str(value or "").strip()

        if not value:
            return ""

        supported_formats = (
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
        )

        for date_format in supported_formats:
            try:
                parsed_date = datetime.strptime(
                    value,
                    date_format,
                )

                return parsed_date.strftime(
                    "%d%m%Y"
                )

            except ValueError:
                continue

        digits = re.sub(
            r"\D",
            "",
            value,
        )

        if len(digits) == 8:
            # Bereits TTMMJJJJ
            if not digits.startswith(("19", "20")):
                return digits

            # JJJJMMTT in TTMMJJJJ umwandeln
            return (
                    digits[6:8]
                    + digits[4:6]
                    + digits[0:4]
            )

        raise ValueError(
            "Das Geburtsdatum muss beispielsweise als "
            "02.07.2000 angegeben werden."
        )

    @staticmethod
    def _gender_for_pdf(value: str) -> str:
        """Überträgt nur die Kennziffer 1 bis 4."""

        value = str(value or "").strip()

        if value and value[0] in "1234":
            return value[0]

        mapping = {
            "weiblich": "1",
            "maennlich": "2",
            "männlich": "2",
            "divers": "3",
            "ohne_angabe": "4",
            "ohne angabe": "4",
        }

        return mapping.get(
            value.lower(),
            value,
        )

    @staticmethod
    def _iban_segments(iban: str) -> dict[str, str]:
        compact = "".join(str(iban).split()).upper()
        chunks = [compact[i : i + 4] for i in range(0, len(compact), 4)]
        chunks = (chunks + [""] * 6)[:6]
        return {f"IBAN {index}": value for index, value in enumerate(chunks, start=1)}

    def build_pdf_values(self, draft: dict[str, dict[str, Any]]) -> dict[str, str]:
        values: dict[str, str] = {}

        for field in draft.values():
            value = str(field.get("value", "")).strip()
            pdf_field = field.get("pdf_field")
            if not value or not pdf_field:
                continue

            if pdf_field == "IBAN":
                values.update(self._iban_segments(value))
                continue

            if pdf_field == "Geschlecht":
                values[pdf_field] = self._gender_for_pdf(
                    value
                )
                continue


            if (
                    pdf_field
                    == "Der Bescheid soll übermittelt werden an"
            ):
                pdf_state = self.NOTICE_RECIPIENT_PDF_STATES.get(
                    value
                )

                if not pdf_state:
                    raise ValueError(
                        "Unbekannte Auswahl für den "
                        f"Bescheidempfänger: {value}"
                    )

                values[pdf_field] = pdf_state
                continue

            if pdf_field == "Geburtsdatum":
                values[pdf_field] = self._birthdate_for_pdf(
                    value
                )
                continue

            if pdf_field in {
                "Bewilligungszeitraum von",
                "Bewilligungszeitraum bis",
            }:
                values[pdf_field] = self._month_year_for_pdf(
                    value
                )
                continue

            if pdf_field in {
                "Vollzeitausbildung",
                "früherer BAföG-Antrag",
                "häusliche Gemeinschaft mit Eltern",
                "Eigentum/Miteigentum der Eltern",
                "Pflegeversicherung",
                "voraussichtliche Einnahmen",
            }:
                values[pdf_field] = self._button(value)
                continue

            if pdf_field == "eigene Kinder":
                values[pdf_field] = self._checkbox(value)
                continue

            if pdf_field == "Krankenversicherung":
                values[pdf_field] = self.INSURANCE_PDF_STATES.get(value, value)
                continue

            if pdf_field == "Familienstand":
                values[pdf_field] = self._family_status(value)
                continue

            if pdf_field == "Verhältnis Elternteile":
                values[pdf_field] = f"/{value}" if not value.startswith("/") else value
                continue

            values[pdf_field] = value

        # Kopfzeile mit Name der auszubildenden Person ergänzen.
        nachname = str(draft.get("nachname", {}).get("value", "")).strip()
        vorname = str(draft.get("vorname", {}).get("value", "")).strip()
        full_name = ", ".join(part for part in [nachname, vorname] if part)
        if full_name:
            values["auszubildende Person"] = full_name

        # Vermögensantwort altersabhängig in das passende
        # Ja-/Nein-Feld des Formblatts übertragen.
        self._add_asset_selection(
            values=values,
            draft=draft,
        )

        return values

    def fill(self, template_path: str | Path, draft: dict[str, dict[str, Any]]) -> bytes:
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF-Vorlage nicht gefunden: {path}")

        reader = PdfReader(str(path))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)

        # PDF-Viewer sollen die Erscheinungsbilder der Felder neu erzeugen.
        if writer._root_object.get("/AcroForm") is not None:  # noqa: SLF001 - pypdf benötigt Zugriff auf AcroForm.
            writer._root_object[NameObject("/AcroForm")][NameObject("/NeedAppearances")] = BooleanObject(True)  # noqa: SLF001

        pdf_values = self.build_pdf_values(draft)
        for page in writer.pages:
            if "/Annots" not in page:
                continue
            try:
                writer.update_page_form_field_values(page, pdf_values, auto_regenerate=False)
            except Exception as exc:  # noqa: BLE001
                # Seiten ohne Formularfelder werfen je nach pypdf-Version eine Meldung/Exception.
                if "No fields to update" not in str(exc):
                    raise

        output = BytesIO()
        writer.write(output)
        return output.getvalue()
