# app/memory/vector_store.py
import chromadb
import uuid
from typing import Optional

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection("gucci_simulation")


def add_documents(texts, metadatas, ids=None):
    if ids is None:
        ids = [f"doc_{uuid.uuid4().hex}" for _ in range(len(texts))]
    collection.add(documents=texts, metadatas=metadatas, ids=ids)


def query_documents(query: str, module: Optional[int] = None, n_results: int = 3):
    where = {"module": module} if module is not None else None
    try:
        if where is None:
            result = collection.query(query_texts=[query], n_results=n_results)
        else:
            result = collection.query(query_texts=[query], n_results=n_results, where=where)
    except Exception:
        return []

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    return list(zip(documents, metadatas))