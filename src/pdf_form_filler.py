from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

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
