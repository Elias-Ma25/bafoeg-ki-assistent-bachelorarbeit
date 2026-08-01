from __future__ import annotations


class ChecklistManager:
    """Erzeugt eine fallabhängige Checkliste für den BAföG-Erstantrag."""

    @staticmethod
    def create_item(
        label: str,
        required: bool = False,
        uploaded: bool = False,
        status: str = "optional",
        reason: str = "",
        source_rule: str = "",
    ) -> dict:
        return {
            "label": label,
            "required": required,
            "uploaded": uploaded,
            "status": status,
            "reason": reason,
            "source_rule": source_rule,
        }

    def create_initial_state(self) -> dict:
        return {
            "formblatt_1": self.create_item(
                "Formblatt 1 – Antrag auf Ausbildungsförderung",
                required=True,
                uploaded=True,
                status="zielformular",
                reason="Das offizielle Formblatt 1 wird vom Assistenten prototypisch vorausgefüllt.",
                source_rule="scope_erstantrag",
            ),
            "studienbescheinigung": self.create_item(
                "Studienbescheinigung nach § 9 BAföG oder Formblatt 02",
                required=True,
                status="offen",
                reason="Dieses Grunddokument wird zu Beginn des Antragsassistenten benötigt.",
                source_rule="required_initial_document",
            ),
            "identitaetsdokument": self.create_item(
                "Personalausweis oder Reisepass",
                status="optional",
                reason="Optional zur automatischen Übernahme persönlicher Daten.",
                source_rule="optional_automation",
            ),
            "vollmacht": self.create_item(
                "Vollmacht für die bevollmächtigte Person",
                required=False,
                status="nicht_erforderlich",
                reason=(
                    "Nur erforderlich, wenn Bescheide und sonstige Schreiben "
                    "an eine bevollmächtigte Person übermittelt werden sollen."
                ),
                source_rule="notice_recipient",
            ),
            "lebenslauf": self.create_item(
                "Lebenslauf",
                status="optional",
                reason="Optional zur Vorbereitung des schulischen und beruflichen Werdegangs.",
                source_rule="optional_automation",
            ),
            "formblatt_3": self.create_item(
                "Formblatt 3 – Einkommenserklärung der Eltern / des Ehepartners",
                required=True,
                status="offen",
                reason=(
                    "Im abgegrenzten Standardfall eines deutschen BAföG-Erstantrags wird Formblatt 3 "
                    "zunächst als relevant vorgemerkt. Sonderfälle wie elternunabhängige Förderung sind nicht Kern des Prototyps."
                ),
                source_rule="scope_standard_case",
            ),
            "formblatt_4": self.create_item(
                "Formblatt 4 – Kinder der auszubildenden Person",
                status="nicht_erforderlich",
                reason="Nur bei eigenen Kindern erforderlich.",
                source_rule="children",
            ),
            "formblatt_5": self.create_item(
                "Formblatt 5 oder Leistungsübersicht nach § 48 BAföG",
                status="nicht_erforderlich",
                reason="Ab dem 5. Fachsemester grundsätzlich zu prüfen.",
                source_rule="semester",
            ),
            "wohnungsnachweis": self.create_item(
                "Wohnungsnachweis (Wohnungsgeberbescheinigung, Meldebescheinigung oder relevante Mietvertragsseiten)",
                status="nicht_erforderlich",
                reason="Erforderlich, wenn nicht mit den Eltern in häuslicher Gemeinschaft gewohnt wird.",
                source_rule="housing",
            ),
            "kranken_pflegeversicherungsnachweis": self.create_item(
                "Bescheinigung über Kranken- und Pflegeversicherung",
                status="nicht_erforderlich",
                reason="Erforderlich, wenn keine gesetzliche Familienversicherung besteht.",
                source_rule="insurance",
            ),
            "einkommensnachweis": self.create_item(
                "Einkommensnachweis",
                status="nicht_erforderlich",
                reason="Erforderlich, wenn im Bewilligungszeitraum eigenes Einkommen vorhanden ist.",
                source_rule="income",
            ),
            "vermoegensnachweis": self.create_item(
                "Vermögensnachweise",
                status="nicht_erforderlich",
                reason="Erforderlich, wenn das Vermögen nicht unter der altersabhängigen Grenze liegt.",
                source_rule="assets",
            ),
            "werdegang_nachweise": self.create_item(
                "Nachweise zum schulischen und beruflichen Werdegang",
                status="zu_pruefen",
                reason=(
                    "Der Lebenslauf kann den Werdegang vorbereiten. Fehlende Zeiträume oder belegpflichtige Zeiten "
                    "müssen anschließend geprüft werden."
                ),
                source_rule="career_review",
            ),
        }

    @staticmethod
    def _value(container: dict, key: str) -> str:
        return str(container.get(key, {}).get("value", "")).strip().lower()

    def apply_case_rules(
            self,
            checklist: dict,
            user_profile: dict,
            case_state: dict,
    ) -> dict:
        # ---------------------------------------------------------
        # Empfänger des Bescheids und Vollmacht
        # ---------------------------------------------------------
        recipient = self._value(
            case_state,
            "bescheid_empfaenger",
        )

        if recipient == "an eine von mir bevollmächtigte person":
            checklist["vollmacht"].update(
                required=True,
                uploaded=False,
                status="offen",
                reason=(
                    "Bescheide und sonstige Schreiben sollen an eine "
                    "bevollmächtigte Person übermittelt werden. "
                    "Daher ist eine entsprechende Vollmacht erforderlich."
                ),
            )

        # ---------------------------------------------------------
        # Eigene Kinder
        # ---------------------------------------------------------
        children = self._value(
            case_state,
            "kinder",
        )

        if children == "ja":
            checklist["formblatt_4"].update(
                required=True,
                status="offen",
                reason=(
                    "Da eigene Kinder angegeben wurden, "
                    "ist Formblatt 4 relevant."
                ),
            )

        # ---------------------------------------------------------
        # Fachsemester
        # ---------------------------------------------------------
        fachsemester = str(
            user_profile.get(
                "fachsemester",
                {},
            ).get(
                "value",
                "",
            )
        ).strip()

        if fachsemester.isdigit() and int(fachsemester) >= 5:
            checklist["formblatt_5"].update(
                required=False,
                status="zu_pruefen",
                reason=(
                    f"Es wurde das {fachsemester}. Fachsemester erkannt. "
                    "Eine Leistungsbescheinigung oder Leistungsübersicht "
                    "sollte geprüft werden."
                ),
            )

        # ---------------------------------------------------------
        # Wohnsituation
        # ---------------------------------------------------------
        housing = self._value(
            case_state,
            "wohnsituation",
        )

        if housing == "nicht_bei_eltern":
            checklist["wohnungsnachweis"].update(
                required=True,
                status="offen",
                reason=(
                    "Du wohnst während der Ausbildung nicht mit "
                    "deinen Eltern zusammen."
                ),
            )

        # ---------------------------------------------------------
        # Kranken- und Pflegeversicherung
        # ---------------------------------------------------------
        insurance = self._value(
            case_state,
            "krankenversicherung",
        )

        if (
                insurance
                and insurance != "familienversichert"
                and insurance != "unklar"
        ):
            checklist[
                "kranken_pflegeversicherungsnachweis"
            ].update(
                required=True,
                status="offen",
                reason=(
                    f"Es wurde die Versicherungsart '{insurance}' "
                    "erkannt; daher ist ein Nachweis relevant."
                ),
            )

        # ---------------------------------------------------------
        # Eigenes Einkommen
        # ---------------------------------------------------------
        income = self._value(
            case_state,
            "eigenes_einkommen",
        )

        if income == "ja":
            checklist["einkommensnachweis"].update(
                required=True,
                status="offen",
                reason=(
                    "Es wurde eigenes Einkommen im "
                    "Bewilligungszeitraum angegeben."
                ),
            )

        # ---------------------------------------------------------
        # Vermögen
        # ---------------------------------------------------------
        assets = self._value(
            case_state,
            "vermoegen_unter_grenze",
        )

        if assets == "nein":
            checklist["vermoegensnachweis"].update(
                required=True,
                status="offen",
                reason=(
                    "Das Vermögen liegt nach der Angabe nicht unter "
                    "der altersabhängigen Grenze."
                ),
            )

        return checklist

    def apply_document_status(self, checklist: dict, document_registry: dict) -> dict:
        mapping = {
            "studienbescheinigung": "studienbescheinigung",
            "identitaetsdokument": "identitaetsdokument",
            "vollmacht": "vollmacht",
            "lebenslauf": "lebenslauf",
            "kranken_pflegeversicherungsnachweis":
                "kranken_pflegeversicherungsnachweis",
            "wohnungsnachweis": "wohnungsnachweis",
            "einkommensnachweis": "einkommensnachweis",
            "vermoegensnachweis": "vermoegensnachweis",
            "leistungsnachweis": "formblatt_5",
        }

        for document_key, checklist_key in mapping.items():
            status = document_registry.get(document_key, {})
            if status.get("uploaded") is True and checklist_key in checklist:
                checklist[checklist_key]["uploaded"] = True
                checklist[checklist_key]["status"] = "vorhanden"
        return checklist

    def update_checklist(self, user_profile: dict, case_state: dict, document_registry: dict) -> dict:
        checklist = self.create_initial_state()
        checklist = self.apply_case_rules(checklist, user_profile, case_state)
        checklist = self.apply_document_status(checklist, document_registry)
        return checklist

    @staticmethod
    def get_missing_items(checklist: dict) -> dict:
        return {
            key: item
            for key, item in checklist.items()
            if item.get("required") is True and item.get("uploaded") is False
        }

    @staticmethod
    def get_uploaded_items(checklist: dict) -> dict:
        return {
            key: item
            for key, item in checklist.items()
            if item.get("uploaded") is True and item.get("status") != "zielformular"
        }
