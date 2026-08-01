\# KI-gestützter BAföG-Assistent



\## Projektbeschreibung



Dieses Projekt entstand im Rahmen einer Bachelorarbeit im Studiengang

Wirtschaftsinformatik.



Thema der Bachelorarbeit:



\*\*Konzeption und prototypische Entwicklung eines KI-gestützten Chatbots

zur Unterstützung administrativer Antragsprozesse am Beispiel BAföG\*\*



Der entwickelte Prototyp unterstützt Studierende bei der Vorbereitung

eines BAföG-Erstantrags. Dabei kombiniert die Anwendung einen freien

Beratungschat, eine dokumentenbasierte Datenextraktion, adaptive

Leitfragen, eine persönliche Nachweis-Checkliste und die Vorausfüllung

von Formblatt 1.



Die Anwendung stellt keine rechtsverbindliche BAföG-Entscheidung dar

und ersetzt weder das zuständige Amt für Ausbildungsförderung noch

BAföG Digital.



\## Zielsetzung



Ziel des Prototyps ist es, den BAföG-Antragsprozess verständlicher,

strukturierter und nutzerfreundlicher zu gestalten.



Die Anwendung soll insbesondere:



\- allgemeine Fragen zur BAföG-Erstantragstellung beantworten,

\- relevante Informationen aus hochgeladenen Dokumenten erkennen,

\- fehlende Angaben durch adaptive Fragen ermitteln,

\- fallabhängige Nachweise in einer Checkliste darstellen,

\- erkannte Angaben zur Kontrolle anzeigen,

\- Korrekturen durch die Nutzer ermöglichen,

\- Formblatt 1 prototypisch vorausfüllen.



\## Unterstützter Anwendungsbereich



Der aktuelle Prototyp konzentriert sich auf folgenden Standardfall:



\- BAföG-Erstantrag,

\- Studium in Deutschland,

\- deutsche antragstellende Person,

\- dokumentenbasierte Vorbereitung von Formblatt 1,

\- elternabhängige Förderung als Standardfall.



Komplexe Sonderfälle wie eine vollständige Auslandsförderung,

Folgeanträge, sämtliche Fälle der elternunabhängigen Förderung oder

eine rechtsverbindliche Berechnung des Förderungsbetrags werden nicht

vollständig unterstützt.



\## Hauptfunktionen



\### Freie BAföG-Beratung



Im freien Chat können allgemeine Fragen zur BAföG-Erstantragstellung

gestellt werden. Die Antworten werden mithilfe einer lokalen

RAG-Wissensbasis aus amtlichen BAföG-Dokumenten unterstützt.



\### Dokumentenanalyse



Zu Beginn des Antragsprozesses wird eine Studienbescheinigung nach

§ 9 BAföG oder Formblatt 2 benötigt.



Weitere Dokumente können optional hochgeladen werden, zum Beispiel:



\- Personalausweis oder Reisepass,

\- Lebenslauf,

\- Kranken- und Pflegeversicherungsnachweis,

\- Wohnungsnachweis,

\- Einkommensnachweis,

\- Vermögensnachweis,

\- Leistungsnachweis.



Die Dokumente werden analysiert und erkannte Angaben strukturiert

gespeichert.



\### Adaptive Leitfragen



Nach der Dokumentenanalyse fragt der Assistent nur Angaben ab, die

noch fehlen oder nicht eindeutig erkannt wurden.



Die Nutzer können entweder:



\- eine Schnellauswahl verwenden oder

\- ihre Situation frei als Text beschreiben.



\### Persönliche Nachweis-Checkliste



Die Checkliste wird anhand der erkannten persönlichen Situation

dynamisch erstellt.



Sie unterscheidet zwischen:



\- bereits vorhandenen Nachweisen,

\- noch erforderlichen Nachweisen,

\- optionalen oder zu prüfenden Nachweisen.



\### Kontrollierbare Formularvorschau



Die unterstützten Angaben für Formblatt 1 werden nach Kategorien

angezeigt.



Nutzer können:



\- erkannte Werte kontrollieren,

\- fehlende Angaben ergänzen,

\- falsche Werte korrigieren,

\- die Angaben abschließend bestätigen.



\### PDF-Vorausfüllung



Nach der Bestätigung kann eine prototypisch vorausgefüllte Version von

Formblatt 1 erzeugt werden.



Die erzeugte PDF muss vor einer möglichen Einreichung vollständig

kontrolliert werden. Nicht unterstützte Felder können leer bleiben.



\## Technischer Aufbau



Der Prototyp verwendet unter anderem:



\- Python

\- Streamlit

\- OpenAI API

\- LangChain

\- ChromaDB

\- Retrieval-Augmented Generation

\- PyPDF

\- PDFPlumber

\- FillPDF

\- ReportLab



\## Projektstruktur



```text

bafoeg\_chatbot\_prototype/

├── app.py

├── requirements.txt

├── README.md

├── .env.example

├── data/

│   ├── knowledge/

│   ├── uploads/

│   └── zwischenablage/

├── Forms/

└── src/

&#x20;   ├── app\_config.py

&#x20;   ├── application\_flow\_manager.py

&#x20;   ├── checklist\_manager.py

&#x20;   ├── checklist\_view.py

&#x20;   ├── document\_processor.py

&#x20;   ├── formblatt1\_manager.py

&#x20;   ├── hybrid\_questions.py

&#x20;   ├── llm\_interpreter.py

&#x20;   ├── pdf\_form\_filler.py

&#x20;   └── rag\_pipeline.py

