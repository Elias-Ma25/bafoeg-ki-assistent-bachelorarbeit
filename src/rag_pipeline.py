from __future__ import annotations
from pathlib import Path
import shutil
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
    knowledge_path = Path(folder_path).resolve()
    vectorstore_path = Path(persist_directory).resolve()

    documents = load_knowledge_documents(
        str(knowledge_path)
    )

    if not documents:
        raise ValueError(
            "Im Wissensordner wurden keine TXT- "
            "oder PDF-Dokumente gefunden."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )

    split_docs = splitter.split_documents(
        documents
    )

    # Bestehenden Store vollständig entfernen.
    # Dadurch bleiben keine alten oder doppelten Chunks zurück.
    if vectorstore_path.exists():
        shutil.rmtree(
            vectorstore_path
        )

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=str(vectorstore_path),
    )

    return vectorstore

def load_vectorstore(persist_directory: str = "chroma_db"):
    embeddings = OpenAIEmbeddings()
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)

def get_relevant_context(
    question: str,
    persist_directory: str = "chroma_db",
    k: int = 5,
) -> str:
    vectorstore = load_vectorstore(
        persist_directory
    )

    # MMR sucht relevante, aber zugleich unterschiedliche Abschnitte.
    # Dadurch stammen nicht alle Treffer aus derselben FAQ oder Datei.
    if hasattr(
        vectorstore,
        "max_marginal_relevance_search",
    ):
        docs = vectorstore.max_marginal_relevance_search(
            question,
            k=k,
            fetch_k=15,
            lambda_mult=0.7,
        )
    else:
        docs = vectorstore.similarity_search(
            question,
            k=k,
        )

    context_parts: list[str] = []

    for doc in docs:
        content = str(
            doc.page_content
        ).strip()

        if not content:
            continue

        source_path = str(
            doc.metadata.get(
                "source",
                "Unbekannte Quelle",
            )
        )

        source_name = Path(
            source_path
        ).name

        page = doc.metadata.get("page")

        if isinstance(page, int):
            source_label = (
                f"{source_name}, Seite {page + 1}"
            )
        else:
            source_label = source_name

        context_parts.append(
            f"[Quelle: {source_label}]\n"
            f"{content}"
        )

    return "\n\n---\n\n".join(
        context_parts
    )
