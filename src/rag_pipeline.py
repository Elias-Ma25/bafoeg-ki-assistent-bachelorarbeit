from __future__ import annotations

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

def build_vectorstore(folder_path: str, persist_directory: str = "chroma_db"):
    documents = load_knowledge_documents(folder_path)
    if not documents:
        raise ValueError("Im Wissensordner wurden keine TXT- oder PDF-Dokumente gefunden.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    split_docs = splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings()
    return Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=persist_directory,
    )

def load_vectorstore(persist_directory: str = "chroma_db"):
    embeddings = OpenAIEmbeddings()
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)

def get_relevant_context(question: str, persist_directory: str = "chroma_db", k: int = 3) -> str:
    vectorstore = load_vectorstore(persist_directory)
    docs = vectorstore.similarity_search(question, k=k)
    return "\n\n".join(doc.page_content for doc in docs)
