from __future__ import annotations

import json
from datetime import datetime
from typing import Any


CASE_FIELD_ALLOWED_VALUES: dict[str, list[str]] = {
    "vollzeitausbildung": ["ja", "nein", "unklar"],
    "wohnsituation": ["bei_eltern", "nicht_bei_eltern", "unklar"],
    "wohnraum_eigentum_eltern": ["ja", "nein", "nicht_relevant", "unklar"],
    "familienstand": [
        "ledig",
        "verheiratet",
        "dauernd_getrennt",
        "verwitwet",
        "geschieden",
        "unklar",
    ],
    "kinder": ["ja", "nein", "unklar"],
    "krankenversicherung": [
        "familienversichert",
        "studentisch_gesetzlich",
        "freiwillig_gesetzlich",
        "privat",
        "anders",
        "unklar",
    ],
    "pflegeversicherung_selbst_beitragspflichtig": ["ja", "nein", "unklar"],
    "eigenes_einkommen": ["ja", "nein", "unklar"],
    "vermoegen_unter_grenze": ["ja", "nein", "unklar"],
}

PROFILE_FIELDS = {"geburtsdatum"}


def create_fallback_result(message: str = "") -> dict[str, Any]:
    text = message or "Ich bin mir nicht sicher, wie ich deine Antwort einordnen soll. Kannst du sie bitte genauer formulieren?"
    return {
        "intent": "unclear",
        "case_updates": {},
        "profile_updates": {},
        "confidence": "low",
        "should_save": False,
        "needs_followup": True,
        "followup_question": text,
        "assistant_answer": text,
        "next_action": "ask_followup",
    }


def _parse_json(raw: str) -> dict:
    raw = str(raw or "").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```")
        raw = raw.removesuffix("```").strip()
    return json.loads(raw)


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized = create_fallback_result()
    if not isinstance(result, dict):
        return normalized

    for key in normalized:
        if key in result:
            normalized[key] = result[key]

    normalized["intent"] = str(normalized.get("intent", "")).strip()
    normalized["confidence"] = str(normalized.get("confidence", "low")).strip().lower()
    normalized["assistant_answer"] = str(normalized.get("assistant_answer", "")).strip()
    normalized["followup_question"] = str(normalized.get("followup_question", "")).strip()
    normalized["next_action"] = str(normalized.get("next_action", "")).strip()
    normalized["should_save"] = bool(normalized.get("should_save", False))
    normalized["needs_followup"] = bool(normalized.get("needs_followup", False))

    if not isinstance(normalized.get("case_updates"), dict):
        normalized["case_updates"] = {}
    if not isinstance(normalized.get("profile_updates"), dict):
        normalized["profile_updates"] = {}

    normalized["case_updates"] = {
        str(k).strip(): str(v).strip() for k, v in normalized["case_updates"].items() if str(v).strip()
    }
    normalized["profile_updates"] = {
        str(k).strip(): str(v).strip() for k, v in normalized["profile_updates"].items() if str(v).strip()
    }
    return normalized


def validate_result(result: dict[str, Any], current_step: dict) -> tuple[bool, str]:
    if result.get("should_save") is not True:
        return True, ""

    if result.get("confidence") not in {"high", "medium"}:
        return False, "Die Interpretation ist nicht sicher genug."

    permitted_case_fields = set(current_step.get("target_fields", [])) & set(CASE_FIELD_ALLOWED_VALUES)
    permitted_profile_fields = set(current_step.get("target_fields", [])) & PROFILE_FIELDS

    case_updates = result.get("case_updates", {})
    profile_updates = result.get("profile_updates", {})

    if not case_updates and not profile_updates:
        return False, "Die KI hat keine speicherbare Angabe geliefert."

    for field, value in case_updates.items():
        if field not in permitted_case_fields:
            return False, f"Das Feld '{field}' gehört nicht zur aktuellen Frage."
        if value not in CASE_FIELD_ALLOWED_VALUES[field] or value == "unklar":
            return False, f"Der Wert '{value}' ist für '{field}' nicht zulässig."

    for field, value in profile_updates.items():
        if field not in permitted_profile_fields:
            return False, f"Das Profilfeld '{field}' gehört nicht zur aktuellen Frage."
        if field == "geburtsdatum":
            try:
                datetime.strptime(value, "%d.%m.%Y")
            except ValueError:
                return False, "Das Geburtsdatum muss im Format TT.MM.JJJJ vorliegen."

    # Kombinierte Wohnfrage: Bei Wohnen mit Eltern wird Eigentum automatisch nicht relevant.
    if current_step.get("key") == "wohnsituation_und_eigentum":
        living = case_updates.get("wohnsituation", "")
        ownership = case_updates.get("wohnraum_eigentum_eltern", "")
        if living == "bei_eltern" and not ownership:
            case_updates["wohnraum_eigentum_eltern"] = "nicht_relevant"
        elif living == "nicht_bei_eltern" and ownership not in {"ja", "nein"}:
            return False, "Bei Wohnen außerhalb des Elternhauses fehlt noch die Angabe zum Eigentum des Wohnraums."

    # Kranken- und Pflegeversicherung werden gemeinsam verarbeitet.
    if current_step.get("key") == "kranken_pflegeversicherung":
        insurance = case_updates.get("krankenversicherung", "")
        if not insurance:
            return False, "Die Versicherungsart wurde nicht erkannt."
        if "pflegeversicherung_selbst_beitragspflichtig" not in case_updates:
            case_updates["pflegeversicherung_selbst_beitragspflichtig"] = (
                "nein" if insurance == "familienversichert" else "ja"
            )

    return True, ""


def build_step_rules(current_key: str, question_text: str) -> str:
    rules = {
        "geburtsdatum": """
- Extrahiere das Geburtsdatum und normalisiere es als TT.MM.JJJJ.
- Speichere es in profile_updates.geburtsdatum.
""",
        "vollzeitausbildung": """
- Vollzeitstudium oder reguläres Vollzeitstudium => vollzeitausbildung = ja.
- Teilzeitstudium, berufsbegleitend oder ausdrücklich nicht Vollzeit => vollzeitausbildung = nein.
""",
        "wohnsituation_und_eigentum": """
- Die Frage enthält zwei mögliche Angaben.
- Wohnen bei Eltern/einem Elternteil => wohnsituation = bei_eltern und wohnraum_eigentum_eltern = nicht_relevant.
- Eigene Wohnung, WG, Wohnheim, bei Verwandten oder andere Wohnung außerhalb des Elternhaushalts => wohnsituation = nicht_bei_eltern.
- Onkel, Tante, Großeltern, Geschwister und andere Verwandte sind in diesem Feld nicht die Eltern.
- Beispiel: „Das Haus gehört meinem Onkel und meine Eltern leben nicht mit mir“ => wohnsituation = nicht_bei_eltern und wohnraum_eigentum_eltern = nein.
- Wenn der Nutzer zusätzlich sagt, dass der Wohnraum den Eltern gehört => wohnraum_eigentum_eltern = ja.
- Wenn er sagt, dass die Wohnung einem Vermieter, ihm selbst, einem Onkel/einer Tante oder einer anderen Person gehört => wohnraum_eigentum_eltern = nein.
- Frage nicht erneut, ob der Onkel ein anderer Verwandter ist; diese Unterscheidung ist für das Zielfeld irrelevant.
- Sagt er nur „nein“ zur ersten Teilfrage, frage gezielt nach dem Eigentum des Wohnraums und speichere noch nichts.
""",
        "familienstand": """
- ledig => ledig
- verheiratet/eingetragene Lebenspartnerschaft => verheiratet
- dauernd getrennt => dauernd_getrennt
- verwitwet => verwitwet
- geschieden/aufgehoben => geschieden
""",
        "kinder": """
- Eigene Kinder vorhanden => kinder = ja.
- Keine eigenen Kinder => kinder = nein.
""",
        "kranken_pflegeversicherung": """
- „über meine Eltern“, „familienversichert“ => krankenversicherung = familienversichert; pflegeversicherung_selbst_beitragspflichtig = nein.
- „studentisch versichert“, „studentische Krankenversicherung“ => krankenversicherung = studentisch_gesetzlich; pflegeversicherung_selbst_beitragspflichtig = ja.
- „freiwillig gesetzlich“ => krankenversicherung = freiwillig_gesetzlich; pflegeversicherung_selbst_beitragspflichtig = ja.
- „privat“ => krankenversicherung = privat; pflegeversicherung_selbst_beitragspflichtig = ja.
- Eine sonstige konkrete Versicherungsform => krankenversicherung = anders.
- Wenn unklar ist, welche Art gemeint ist, stelle eine Rückfrage und wiederhole kurz die Antwortmöglichkeiten.
""",
        "eigenes_einkommen": """
- Minijob, Werkstudentenjob, Beschäftigung, Praktikumsvergütung, Rente oder andere Einnahmen => eigenes_einkommen = ja.
- Ausdrücklich kein eigenes Einkommen im Bewilligungszeitraum => eigenes_einkommen = nein.
- Eine bloße Frage danach, was Einkommen oder der Bewilligungszeitraum ist, darf nicht gespeichert werden.
- Der Bewilligungszeitraum ist der Zeitraum, für den die Person BAföG beantragt.
- Sind bewilligungszeitraum_von und bewilligungszeitraum_bis im Nutzerprofil bekannt, nenne genau diese Werte.
- Sind sie nicht bekannt, erkläre den Begriff ohne konkrete Beispieljahre als aktuelle Nutzerdaten darzustellen und weise darauf hin, dass Beginn und Ende später angegeben werden.
""",
        "vermoegen_unter_grenze": f"""
- Interpretiere die konkrete altersabhängige Grenze aus der aktuellen Frage: {question_text}
- Liegt das genannte Vermögen unter der dort genannten Grenze => vermoegen_unter_grenze = ja.
- Liegt es darüber => vermoegen_unter_grenze = nein.
- Wenn der Nutzer keine klare Aussage macht, frage nach.
""",
    }
    return rules.get(current_key, "")


def interpret_adaptive_application_message(
    client,
    model: str,
    user_message: str,
    current_step: dict,
    rendered_question: str,
    user_profile: dict,
    case_state: dict,
    context: str = "",
    available_options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Interpretiert eine freie Antwort auf eine adaptive Frage.

    Die Funktion entscheidet nur. Gespeichert wird erst nach serverseitiger Validierung.
    """
    if client is None:
        return create_fallback_result("Kein OpenAI API-Key gefunden.")

    known_profile = {
        key: {
            "value": field.get("value", ""),
            "source": field.get("source", ""),
            "confidence": field.get("confidence", ""),
        }
        for key, field in user_profile.items()
    }
    known_case = {
        key: {
            "value": field.get("value", ""),
            "source": field.get("source", ""),
            "confidence": field.get("confidence", ""),
        }
        for key, field in case_state.items()
    }

    available_options = available_options or []
    option_descriptions = [
        {
            "label": str(option.get("label", "")).strip(),
            "case_updates": option.get("case_updates", {}),
            "profile_updates": option.get("profile_updates", {}),
        }
        for option in available_options
    ]

    system_prompt = """
Du bist ein intelligenter BAföG-Erstantragsassistent.
Du interpretierst freie Antworten auf genau eine aktuelle Frage.
Du darfst selbst nichts speichern und musst ausschließlich JSON liefern.

Regeln:
- Sprich in assistant_answer mit „du“.
- Erfinde keine Angaben.
- Speichere nur Angaben, die aus der Nachricht eindeutig hervorgehen.
- Die aktuelle Frage kann mehrere Zielfelder enthalten.
- Allgemeine Rückfragen werden zuerst verständlich beantwortet, ohne Daten zu speichern.
- Wenn die Person fragt, welche Option zu ihrer Situation passt, gib eine begründete Empfehlung,
  speichere aber noch nichts. Bitte anschließend um Bestätigung.
- Eine Frage, Unsicherheit oder Bitte um Erklärung ist keine bestätigte Antragsangabe.
- Nenne bei Erklärungen die verfügbaren Auswahlmöglichkeiten in einfacher Sprache.
- Bei Unklarheit stelle höchstens eine konkrete, kurze Rückfrage.
"""

    user_prompt = f"""
Aktueller Schritt: {current_step.get('key')}
Aktuelle Frage: {rendered_question}
Hilfetext: {current_step.get('help', '')}
Erlaubte Zielfelder: {current_step.get('target_fields', [])}
Erlaubte Fallwerte: {CASE_FIELD_ALLOWED_VALUES}
Sichtbare Schnellauswahlen: {option_descriptions}
Bekanntes Nutzerprofil: {known_profile}
Bekannter Fallstatus: {known_case}
Optionaler BAföG-Kontext aus der Wissensbasis: {context}
Spezielle Regeln: {build_step_rules(current_step.get('key', ''), rendered_question)}

Nutzereingabe:
{user_message}

Gib ausschließlich JSON in dieser Struktur zurück:
{{
  "intent": "answer|explanation_request|general_question|unclear",
  "case_updates": {{"feld": "wert"}},
  "profile_updates": {{"feld": "wert"}},
  "confidence": "high|medium|low",
  "should_save": true oder false,
  "needs_followup": true oder false,
  "followup_question": "Rückfrage oder leer",
  "assistant_answer": "kurze natürliche Antwort",
  "next_action": "continue|answer_only|ask_followup"
}}
"""

    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=700,
        )
        parsed = _parse_json(completion.choices[0].message.content)
        return normalize_result(parsed)
    except Exception as exc:  # noqa: BLE001 - Fehlermeldung wird nutzerfreundlich weitergegeben.
        return create_fallback_result(f"Ich konnte deine Antwort gerade nicht sicher interpretieren: {exc}")

def explain_application_step(
    client,
    model: str,
    current_step: dict,
    rendered_question: str,
    user_profile: dict,
    case_state: dict,
    available_options: list[dict[str, Any]] | None = None,
    context: str = "",
    mode: str = "explain",
) -> str:
    """Erklärt die aktuelle Formularfrage, ohne Daten zu speichern.

    Erklärt Bedeutung und Auswahlmöglichkeiten der aktuellen Frage.
    """
    available_options = available_options or []
    option_labels = [
        str(option.get("label", "")).strip()
        for option in available_options
        if str(option.get("label", "")).strip()
    ]

    fallback_parts = [
        str(current_step.get("help", "")).strip(),
    ]
    if option_labels:
        fallback_parts.append(
            "Du kannst zwischen folgenden Möglichkeiten wählen:\n- "
            + "\n- ".join(option_labels)
        )
    fallback = "\n\n".join(part for part in fallback_parts if part).strip()
    if not fallback:
        fallback = rendered_question

    if client is None:
        return fallback

    known_profile = {
        key: str(field.get("value", "")).strip()
        for key, field in user_profile.items()
        if str(field.get("value", "")).strip()
    }
    known_case = {
        key: str(field.get("value", "")).strip()
        for key, field in case_state.items()
        if str(field.get("value", "")).strip()
    }

    task = (
        "Erkläre die Frage und die Unterschiede zwischen den Auswahlmöglichkeiten."
        if mode == "explain"
        else (
            "Prüfe anhand der bereits bekannten Angaben, welche Auswahl wahrscheinlich passt. "
            "Wenn die Informationen nicht reichen, stelle genau eine kurze Rückfrage. "
            "Speichere oder bestätige keine Auswahl."
        )
    )

    prompt = f"""
Du bist ein vorsichtiger KI-Assistent für einen deutschen BAföG-Erstantrag.
{task}

Aktuelle Frage:
{rendered_question}

Hilfetext:
{current_step.get("help", "")}

Auswahlmöglichkeiten:
{option_labels}

Bereits bekannte Profilangaben:
{known_profile}

Bereits bekannte Fallangaben:
{known_case}

Kontext aus der BAföG-Wissensbasis:
{context}

Regeln:
- Antworte verständlich und knapp.
- Erfinde keine Tatsachen.
- Triff keine rechtsverbindliche Entscheidung.
- Sage bei einer Empfehlung ausdrücklich „wahrscheinlich“.
- Bitte um Bestätigung, bevor eine Auswahl übernommen wird.
- Gib normalen Text und kein JSON zurück.
""".strip()

    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du erklärst genau eine BAföG-Formularfrage. "
                        "Du speicherst keine Angaben."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
        )
        answer = str(completion.choices[0].message.content or "").strip()
        return answer or fallback
    except Exception:
        return fallback
