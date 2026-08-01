from __future__ import annotations

from collections import OrderedDict
from typing import Any


class Formblatt1Manager:
    """Erstellt eine bearbeitbare Vorschau für ausgewählte Felder von Formblatt 1."""

    INSURANCE_LABELS = {
        "familienversichert": "gesetzlich familienversichert",
        "studentisch_gesetzlich": "studentisch gesetzlich versichert",
        "freiwillig_gesetzlich": "freiwillig gesetzlich versichert",
        "privat": "privat versichert",
        "anders": "anders versichert",
    }

    FAMILY_STATUS_LABELS = {
        "ledig": "1 – ledig",
        "verheiratet": "2 – verheiratet / eingetragene Lebenspartnerschaft",
        "dauernd_getrennt": "3 – dauernd getrennt lebend",
        "verwitwet": "4 – verwitwet",
        "geschieden": "5 – geschieden / aufgehoben",
    }

    GENDER_LABELS = {
        "weiblich": "1",
        "maennlich": "2",
        "divers": "3",
        "ohne_angabe": "4",
    }
    NOTICE_RECIPIENT_OPTIONS = [
        "An mich – ständiger Wohnsitz",
        "An mich – Anschrift während der Ausbildung",
        "An meinen ersten Elternteil",
        "An meinen zweiten Elternteil",
        "An meine sorgeberechtigte Person",
        "An eine von mir bevollmächtigte Person",
    ]

    @staticmethod
    def _metadata_field(
        field_id: str,
        section: str,
        label: str,
        value: str = "",
        source: str = "",
        confidence: str = "",
        status: str = "offen",
        input_type: str = "text",
        options: list[str] | None = None,
        required: bool = False,
        pdf_field: str | None = None,
        help_text: str = "",
    ) -> dict[str, Any]:
        return {
            "id": field_id,
            "section": section,
            "label": label,
            "value": str(value or ""),
            "source": source,
            "confidence": confidence,
            "status": status,
            "input_type": input_type,
            "options": options or [],
            "required": required,
            "pdf_field": pdf_field,
            "help": help_text,
        }

    @staticmethod
    def _read(container: dict, key: str) -> tuple[str, str, str]:
        field = container.get(key, {})
        return (
            str(field.get("value", "")).strip(),
            str(field.get("source", "")).strip(),
            str(field.get("confidence", "")).strip(),
        )

    def _from_profile(
        self,
        user_profile: dict,
        field_id: str,
        section: str,
        label: str,
        profile_key: str,
        **kwargs,
    ) -> dict:
        value, source, confidence = self._read(user_profile, profile_key)
        return self._metadata_field(
            field_id,
            section,
            label,
            value=value,
            source=source,
            confidence=confidence,
            status="übernommen" if value else "offen",
            **kwargs,
        )

    def _from_case(
        self,
        case_state: dict,
        field_id: str,
        section: str,
        label: str,
        case_key: str,
        transform=None,
        **kwargs,
    ) -> dict:
        value, source, confidence = self._read(case_state, case_key)
        if value and transform:
            value = transform(value)
        return self._metadata_field(
            field_id,
            section,
            label,
            value=value,
            source=source,
            confidence=confidence,
            status="beantwortet" if value else "offen",
            **kwargs,
        )

    @staticmethod
    def _yes_no(value: str) -> str:
        mapping = {
            "ja": "ja",
            "nein": "nein",
            "bei_eltern": "ja",
            "nicht_bei_eltern": "nein",
            "nicht_relevant": "",
        }
        return mapping.get(str(value).lower(), str(value))

    def build_draft(
            self,
            user_profile: dict,
            case_state: dict,
            career_entries: list[dict] | None = None,
            career_row_count: int = 1,
            manual_values: dict[str, str] | None = None,
    ) -> OrderedDict[str, dict[str, Any]]:
        """Erzeugt rund 40 unterstützte Formblattfelder plus Werdegangszeilen."""
        manual_values = manual_values or {}
        career_entries = career_entries or []
        career_row_count = max(
            1,
            min(int(career_row_count or 1), 8),
        )
        fields: OrderedDict[str, dict[str, Any]] = OrderedDict()

        def add(field: dict[str, Any]) -> None:
            manual_value = str(manual_values.get(field["id"], "")).strip()
            if field["id"] in manual_values:
                field["value"] = manual_value
                field["source"] = "user_confirmed"
                field["confidence"] = "high"
                field["status"] = "manuell_bestaetigt" if manual_value else "offen"
            fields[field["id"]] = field

        # Ausbildung
        hochschule, hochschule_source, hochschule_conf = self._read(user_profile, "hochschule")
        ausbildungsort, ort_source, ort_conf = self._read(user_profile, "ausbildungsort")
        combined_school = " – ".join(part for part in [hochschule, ausbildungsort] if part)
        add(
            self._metadata_field(
                "ausbildungsstaette_ort",
                "Ausbildung",
                "Ausbildungsstätte und Ausbildungsort",
                combined_school,
                source=hochschule_source or ort_source,
                confidence=hochschule_conf or ort_conf,
                status="übernommen" if combined_school else "offen",
                required=True,
                pdf_field="Ausbildungsstätte und Ausbildungsort",
            )
        )
        add(self._from_profile(user_profile, "studiengang", "Ausbildung", "Klasse/Fachrichtung / Studiengang", "studiengang", required=True, pdf_field="Klasse/Fachrichtung"))
        add(self._from_profile(user_profile, "abschlussziel", "Ausbildung", "Angestrebter Abschluss", "abschlussziel", required=True, pdf_field="angestrebter Abschluss"))
        add(self._from_case(case_state, "vollzeitausbildung", "Ausbildung", "Vollzeitausbildung", "vollzeitausbildung", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], required=True, pdf_field="Vollzeitausbildung"))
        add(self._metadata_field("frueherer_bafoeg_antrag", "Ausbildung", "Bereits früher BAföG beantragt", "nein", source="scope_erstantrag", confidence="high", status="systemvorgabe", input_type="select", options=["nein"], required=True, pdf_field="früherer BAföG-Antrag"))

        # Person
        add(self._from_profile(user_profile, "nachname", "Person", "Nachname", "nachname", required=True, pdf_field="Name"))
        add(self._from_profile(user_profile, "vorname", "Person", "Vorname", "vorname", required=True, pdf_field="Vorname"))
        geburtsname, geburtsname_source, geburtsname_confidence = self._read(
            user_profile,
            "geburtsname",
        )
        add(
            self._metadata_field(
                "geburtsname",
                "Person",
                "Geburtsname (falls abweichend)",
                value=geburtsname or "-",
                source=(
                    geburtsname_source
                    if geburtsname
                    else "system_default_no_birth_name"
                ),
                confidence=(
                    geburtsname_confidence
                    if geburtsname
                    else "high"
                ),
                status=(
                    "übernommen"
                    if geburtsname
                    else "systemvorgabe"
                ),
                pdf_field="Geburtsname",
                help_text=(
                    "Ist kein abweichender Geburtsname bekannt, wird „-“ "
                    "verwendet. Falls du einen Geburtsnamen hast, ändere den Wert."
                ),
            )
        )
        add(self._from_profile(user_profile, "geburtsdatum", "Person", "Geburtsdatum", "geburtsdatum", required=True, pdf_field="Geburtsdatum"))
        add(self._from_case(case_state, "familienstand", "Person", "Familienstand", "familienstand", transform=lambda v: self.FAMILY_STATUS_LABELS.get(v, v), input_type="select", options=["", *self.FAMILY_STATUS_LABELS.values()], required=True, pdf_field="Familienstand"))
        add(self._from_profile(user_profile, "geburtsort", "Person", "Geburtsort", "geburtsort", required=True, pdf_field="Geburtsort"))
        gender_value, gender_source, gender_confidence = self._read(user_profile, "geschlecht")
        add(
            self._metadata_field(
                "geschlecht",
                "Person",
                "Geschlecht (w/m/d)",
                self.GENDER_LABELS.get(gender_value, gender_value),
                source=gender_source,
                confidence=gender_confidence,
                status="übernommen" if gender_value else "offen",
                input_type="select",
                options=["", "1_weiblich", "2_männlich", "3_divers", "4_ohne Angabe (gemäß Geburtenregister)"],
                required=True,
                pdf_field="Geschlecht",
            )
        )
        add(self._metadata_field("staatsangehoerigkeit", "Person", "Eigene Staatsangehörigkeit", "deutsch", source="scope_deutsche_antragsteller", confidence="high", status="systemvorgabe", required=True, pdf_field="eigene Staatsangehörigkeit"))
        add(self._from_case(case_state, "kinder", "Person", "Eigene Kinder", "kinder", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], required=True, pdf_field="eigene Kinder"))

        # Ständiger Wohnsitz
        for field_id, label, profile_key, pdf_field in [
            ("anschrift_strasse", "Straße", "anschrift_strasse", "Anschrift Straße"),
            ("anschrift_hausnummer", "Hausnummer", "anschrift_hausnummer", "Anschrift Hausnummer"),
            ("anschrift_land", "Land", "anschrift_land", "Anschrift Land"),
            ("anschrift_plz", "Postleitzahl", "anschrift_plz", "Anschrift Postleitzahl"),
            ("anschrift_ort", "Ort", "anschrift_ort", "Anschrift Ort"),
        ]:
            add(
                self._from_profile(
                    user_profile,
                    field_id,
                    "Ständiger Wohnsitz",
                    label,
                    profile_key,
                    required=True,
                    pdf_field=pdf_field,
                )
            )

        add(self._from_case(case_state, "wohnsituation", "Wohnsituation", "Mit Eltern/einem Elternteil in häuslicher Gemeinschaft", "wohnsituation", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], required=True, pdf_field="häusliche Gemeinschaft mit Eltern"))
        add(self._from_case(case_state, "wohnraum_eigentum_eltern", "Wohnsituation", "Wohnraum im Eigentum/Miteigentum der Eltern", "wohnraum_eigentum_eltern", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], pdf_field="Eigentum/Miteigentum der Eltern"))

        # Anschrift während Ausbildung
        for field_id, label, profile_key, pdf_field in [
            ("ausbildung_strasse", "Straße am Ausbildungsort", "ausbildung_strasse", "Anschrift Ausbildung Straße"),
            ("ausbildung_hausnummer", "Hausnummer am Ausbildungsort", "ausbildung_hausnummer", "Anschrift Ausbildung Hausnummer"),
            ("ausbildung_land", "Land am Ausbildungsort", "ausbildung_land", "Anschrift Ausbildung Land"),
            ("ausbildung_plz", "Postleitzahl am Ausbildungsort", "ausbildung_plz", "Anschrift Ausbildung Postleitzahl"),
            ("ausbildung_ort", "Ort am Ausbildungsort", "ausbildung_ort", "Anschrift Ausbildung Ort"),
        ]:
            add(
                self._from_profile(
                    user_profile,
                    field_id,
                    "Anschrift während der Ausbildung",
                    label,
                    profile_key,
                    pdf_field=pdf_field,
                )
            )

        # Kontakt und Bank
        add(self._from_profile(user_profile, "telefon", "Kontakt und Bank", "Telefon", "telefon", pdf_field="Kontaktdaten Telefon"))
        add(self._from_profile(user_profile, "email", "Kontakt und Bank", "E-Mail", "email", pdf_field="Kontaktdaten E-Mail"))
        add(
            self._from_case(
                case_state=case_state,
                field_id="bescheid_empfaenger",
                section="Kontakt und Bank",
                label="Bescheid und sonstige Schreiben übermitteln an",
                case_key="bescheid_empfaenger",
                input_type="select",
                options=self.NOTICE_RECIPIENT_OPTIONS,
                required=True,
                help_text=(
                    "Standardmäßig werden der Bescheid und sonstige Schreiben "
                    "an die antragstellende Person am ständigen Wohnsitz "
                    "übermittelt. Wähle eine andere Option, falls die Schreiben "
                    "an eine andere Anschrift oder Person gesendet werden sollen."
                ),
            )
        )
        add(self._from_profile(user_profile, "iban", "Kontakt und Bank", "IBAN", "iban", required=True, pdf_field="IBAN"))
        add(self._from_profile(user_profile, "geldinstitut", "Kontakt und Bank", "Name des Geldinstituts", "geldinstitut", required=True, pdf_field="Name Geldistitut"))
        kontoinhaber, kontoinhaber_source, kontoinhaber_confidence = self._read(
            user_profile,
            "kontoinhaber",
        )
        vorname, _, _ = self._read(user_profile, "vorname")
        nachname, _, _ = self._read(user_profile, "nachname")
        antragsteller_name = " ".join(
            part for part in [vorname, nachname] if part
        )

        effective_account_holder = kontoinhaber or antragsteller_name
        add(
            self._metadata_field(
                "kontoinhaber",
                "Kontakt und Bank",
                (
                    "Kontoinhaber – ändern, falls das Konto nicht "
                    "auf deinen Namen läuft"
                ),
                value=effective_account_holder,
                source=(
                    kontoinhaber_source
                    if kontoinhaber
                    else (
                        "derived_applicant_name"
                        if antragsteller_name
                        else ""
                    )
                ),
                confidence=(
                    kontoinhaber_confidence
                    if kontoinhaber
                    else ("high" if antragsteller_name else "")
                ),
                status=(
                    "übernommen"
                    if kontoinhaber
                    else (
                        "abgeleitet"
                        if antragsteller_name
                        else "offen"
                    )
                ),
                pdf_field="Name, Vorname Kontoinhaber",
                help_text=(
                    "Standardmäßig wird der Name der antragstellenden Person "
                    "eingetragen. Ändere den Wert nur, wenn das Konto auf eine "
                    "andere Person läuft."
                ),
            )
        )

        # Versicherung
        add(self._from_case(case_state, "krankenversicherung", "Kranken- und Pflegeversicherung", "Krankenversicherung", "krankenversicherung", transform=lambda v: self.INSURANCE_LABELS.get(v, v), input_type="select", options=["", *self.INSURANCE_LABELS.values()], required=True, pdf_field="Krankenversicherung"))
        add(self._from_case(case_state, "pflegeversicherung", "Kranken- und Pflegeversicherung", "Selbst beitragspflichtig pflegeversichert", "pflegeversicherung_selbst_beitragspflichtig", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], required=True, pdf_field="Pflegeversicherung"))
        add(self._from_profile(user_profile, "steuer_id", "Kranken- und Pflegeversicherung", "Steueridentifikationsnummer", "steuer_id", required=True, pdf_field="Steueridentifikationsnummer"))

        # Eltern – bewusst nur Kernfelder als Stichprobe
        for field_id, label, profile_key, pdf_field in [
            ("elternteil1_nachname", "Nachname 1. Elternteil", "elternteil1_nachname", "Name 1. Elternteil"),
            ("elternteil1_vorname", "Vorname 1. Elternteil", "elternteil1_vorname", "Vorname Name 1. Elternteil"),
            ("elternteil2_nachname", "Nachname 2. Elternteil", "elternteil2_nachname", "Name 2. Elternteil"),
            ("elternteil2_vorname", "Vorname 2. Elternteil", "elternteil2_vorname", "Vorname Name 2. Elternteil"),
        ]:
            add(self._from_profile(user_profile, field_id, "Eltern", label, profile_key, required=True, pdf_field=pdf_field))
        add(self._from_case(case_state, "verhaeltnis_elternteile", "Eltern",
                            "Meine Elternteile leben und sind miteinander verheiratet oder in eingetragener Lebenspartnerschaft verbunden", "verhaeltnis_elternteile", input_type="select", options=["", "ja", "ja, aber dauernd getrennt lebend", "nein"], pdf_field="Verhältnis Elternteile"))

        # Einkommen und Vermögen
        add(self._from_case(case_state, "eigenes_einkommen", "Einkommen", "Voraussichtliche Einnahmen im Bewilligungszeitraum", "eigenes_einkommen", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], required=True, pdf_field="voraussichtliche Einnahmen"))
        add(self._from_profile(user_profile, "bewilligungszeitraum_von", "Einkommen", "Bewilligungszeitraum von (MM.YYYY)", "bewilligungszeitraum_von", required=True, pdf_field="Bewilligungszeitraum von"))
        add(self._from_profile(user_profile, "bewilligungszeitraum_bis", "Einkommen", "Bewilligungszeitraum bis (MM.YYYY)", "bewilligungszeitraum_bis", required=True, pdf_field="Bewilligungszeitraum bis"))
        add(self._from_case(case_state, "vermoegen_unter_grenze", "Vermögen", "Vermögen unter der altersabhängigen Grenze", "vermoegen_unter_grenze", transform=self._yes_no, input_type="select", options=["", "ja", "nein"], required=True, help_text="Dieses Feld wird in der Vorschau genutzt. Die hochgeladene PDF-Vorlage enthält möglicherweise veraltete Grenzbeträge und wird deshalb nicht automatisch dafür angekreuzt."))

        # # Werdegang aus Lebenslauf
        # for index, entry in enumerate(career_entries[:8], start=1):
        #     section = "Schulischer und beruflicher Werdegang"
        #     for suffix, label, value, pdf_field in [
        #         ("von", f"Station {index}: von", entry.get("von", ""), f"Monat / Jahr von {index}"),
        #         ("bis", f"Station {index}: bis", entry.get("bis", ""), f"Monat / Jahr bis {index}"),
        #         ("name_ort", f"Station {index}: Ausbildungsstätte/Arbeitgeber und Ort", entry.get("name_ort", ""), f"Name und Ort {index}"),
        #         ("art", f"Station {index}: Schulart/Fachrichtung/Tätigkeit", entry.get("art", ""), f"Schulart/Fachrichtung/Tätigkeit {index}"),
        #         ("abschluss", f"Station {index}: Abschluss/Bruttolohn/Leistung", entry.get("abschluss_leistung", ""), f"Abschluss / Bruttolohn /Leistung {index}"),
        #     ]:
        #         add(self._metadata_field(f"werdegang_{index}_{suffix}", section, label, value, source="lebenslauf", confidence="medium", status="übernommen" if value else "offen", pdf_field=pdf_field))
        #
        # Schulischer und beruflicher Werdegang
        section = "Schulischer und beruflicher Werdegang"

        # Auch ohne hochgeladenen Lebenslauf wird eine leere Station angelegt.
        # Dadurch bleibt der Pflichtbereich immer sichtbar.
        entries_for_draft = [
            dict(entry)
            for entry in career_entries[:8]
        ]

        desired_entry_count = max(
            1,
            career_row_count,
            len(entries_for_draft),
        )

        while len(entries_for_draft) < desired_entry_count:
            entries_for_draft.append({})

        for index, entry in enumerate(entries_for_draft, start=1):
            station_fields = [
                (
                    "von",
                    f"Station {index}: von",
                    entry.get("von", ""),
                    f"Monat / Jahr von {index}",
                    True,
                ),
                (
                    "bis",
                    f"Station {index}: bis",
                    entry.get("bis", ""),
                    f"Monat / Jahr bis {index}",
                    True,
                ),
                (
                    "name_ort",
                    (
                        f"Station {index}: "
                        "Ausbildungsstätte/Arbeitgeber und Ort"
                    ),
                    entry.get("name_ort", ""),
                    f"Name und Ort {index}",
                    True,
                ),
                (
                    "art",
                    (
                        f"Station {index}: "
                        "Schulart/Fachrichtung/Tätigkeit"
                    ),
                    entry.get("art", ""),
                    f"Schulart/Fachrichtung/Tätigkeit {index}",
                    True,
                ),
                (
                    "abschluss",
                    (
                        f"Station {index}: "
                        "Abschluss/Bruttolohn/Leistung"
                    ),
                    entry.get("abschluss_leistung", ""),
                    f"Abschluss / Bruttolohn /Leistung {index}",
                    False,
                ),
            ]

            for (
                suffix,
                label,
                value,
                pdf_field,
                required,
            ) in station_fields:
                value = str(value or "").strip()

                add(
                    self._metadata_field(
                        field_id=f"werdegang_{index}_{suffix}",
                        section=section,
                        label=label,
                        value=value,
                        source=(
                            "lebenslauf"
                            if value and career_entries
                            else ""
                        ),
                        confidence=(
                            "medium"
                            if value and career_entries
                            else ""
                        ),
                        status=(
                            "übernommen"
                            if value
                            else "offen"
                        ),
                        required=required,
                        pdf_field=pdf_field,
                        help_text=(
                            "Bitte laden Sie einen Lebenslauf hoch "
                            "oder tragen Sie den schulischen und "
                            "beruflichen Werdegang manuell ein."
                            if index == 1 and suffix == "von"
                            else ""
                        ),
                    )
                )
        return fields

    @staticmethod
    def calculate_progress(draft: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
        total = len(draft)
        filled = sum(1 for field in draft.values() if str(field.get("value", "")).strip())
        required_fields = [field for field in draft.values() if field.get("required")]
        required_filled = sum(1 for field in required_fields if str(field.get("value", "")).strip())
        return {
            "total": total,
            "filled": filled,
            "open": total - filled,
            "percentage": round(filled / total * 100, 1) if total else 100.0,
            "required_total": len(required_fields),
            "required_filled": required_filled,
            "required_open": len(required_fields) - required_filled,
        }

    @staticmethod
    def get_open_fields(draft: OrderedDict[str, dict[str, Any]], required_only: bool = False) -> list[dict[str, Any]]:
        result = []
        for field in draft.values():
            if required_only and not field.get("required"):
                continue
            if not str(field.get("value", "")).strip():
                result.append(field)
        return result