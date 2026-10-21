from __future__ import annotations
from pathlib import Path

import os

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

def load_knowledge_documents(folder_path: str):
    documents = []
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Wissensordner nicht gefunden: {folder_path}")

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.lower().endswith(".txt"):
            documents.extend(TextLoader(file_path, encoding="utf-8").load())
        elif filename.lower().endswith(".pdf"):
            documents.extend(PyPDFLoader(file_path).load())
    return documents


def build_vectorstore(
    folder_path: str,
    persist_directory: str = "chroma_db",
):
    documents = load_knowledge_documents(folder_path)

    if not documents:
        raise ValueError(
            "Im Wissensordner wurden keine Dokumente gefunden."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )
    split_docs = splitter.split_documents(documents)

    if not split_docs:
        raise ValueError("Keine Textabschnitte erzeugt.")

    print("\n=== WISSENSBASIS NEU AUFBAUEN ===", flush=True)
    print("Wissensordner:", folder_path, flush=True)
    print("Chroma-Verzeichnis:", persist_directory, flush=True)
    print("Quelldokumente/Seiten:", len(documents), flush=True)
    print("Neue Chunks:", len(split_docs), flush=True)

    # Prüfen, ob die gesuchte Rechtsinformation
    # bereits im eingelesenen Material vorhanden ist.
    found = any(
        "teilzeitausbildungen sind nicht förderungsfähig"
        in doc.page_content.lower()
        for doc in documents
    )
    print("Teilzeit-Regel im Quelltext gefunden:", found, flush=True)

    embeddings = OpenAIEmbeddings()

    # Bestehende Sammlung öffnen
    old_store = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings,
    )

    print(
        "Vorher gespeicherte Chunks:",
        old_store._collection.count(),
        flush=True,
    )

    # WICHTIG: Alte Sammlung wirklich löschen.
    old_store.delete_collection()
    del old_store

    # Neue Sammlung mit den aktuellen Dokumenten erzeugen.
    vectorstore = Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=persist_directory,
    )

    new_count = vectorstore._collection.count()

    print("Nachher gespeicherte Chunks:", new_count, flush=True)
    print("Erwartete Chunks:", len(split_docs), flush=True)
    print("================================\n", flush=True)

    if new_count != len(split_docs):
        raise RuntimeError(
            "Die Anzahl gespeicherter Chunks stimmt "
            "nicht mit der Anzahl neuer Chunks überein."
        )

    return vectorstore

def load_vectorstore(persist_directory: str = "chroma_db"):
    embeddings = OpenAIEmbeddings()
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)

def get_relevant_context(
    question: str,
    persist_directory: str = "chroma_db",
    k: int = 10,
) -> str:
    vectorstore = load_vectorstore(persist_directory)

    # Testweise reine Ähnlichkeitssuche statt MMR
    docs = vectorstore.similarity_search(
        question,
        k=k,
    )

    # Debug-Ausgabe der gefundenen Textabschnitte
    print("\n=== RAG-SUCHERGEBNISSE ===", flush=True)
    print("Frage:", question, flush=True)

    for i, doc in enumerate(docs, 1):
        print(f"\nTreffer {i}", flush=True)
        print(
            "Quelle:",
            doc.metadata.get("source"),
            flush=True,
        )
        print(
            "Inhalt:",
            doc.page_content[:800],
            flush=True,
        )

    print("========================\n", flush=True)

    context_parts: list[str] = []

    for doc in docs:
        content = str(doc.page_content).strip()

        if not content:
            continue

        source_path = str(
            doc.metadata.get("source", "Unbekannte Quelle")
        )
        source_name = Path(source_path).name

        page = doc.metadata.get("page")

        if isinstance(page, int):
            source_label = f"{source_name}, Seite {page + 1}"
        else:
            source_label = source_name

        context_parts.append(
            f"[Quelle: {source_label}]\n{content}"
        )

    return "\n\n---\n\n".join(context_parts)

