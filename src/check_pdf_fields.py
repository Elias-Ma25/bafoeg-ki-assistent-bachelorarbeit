from pathlib import Path
from pypdf import PdfReader

pdf_path = Path(__file__).resolve().parent.parent / "formblatt_1.pdf"

reader = PdfReader(pdf_path)
fields = reader.get_fields()

print("ALLE PDF-FORMULARFELDER UND AUSWAHLWERTE\n")

for field_name, field in fields.items():
    print(f"\nFeldname: {field_name}")
    print(f"Feldtyp: {field.get('/FT', 'Unbekannt')}")

    widgets = field.get("/Kids", [])

    if not widgets:
        widgets = [field]

    found_states = set()


    direct_states = field.get("/_States_")
    if direct_states:
        for state in direct_states:
            found_states.add(str(state))

    for widget_ref in widgets:
        widget = widget_ref.get_object()

        appearance = widget.get("/AP")
        if not appearance:
            continue

        normal_appearance = appearance.get("/N")
        if not normal_appearance:
            continue

        states = normal_appearance.get_object()

        if isinstance(states, dict):
            for state in states.keys():
                found_states.add(str(state))

    if found_states:
        print("Interne Auswahlwerte:")
        for state in sorted(found_states):
            print(f"  {state}")
    else:
        print("Keine Auswahlwerte (z. B. normales Textfeld)")

print("\n=== ENDE ===")