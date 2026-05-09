
import chromadb
import uuid
from typing import Optional, Any

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection("gucci_simulation")


def _clean_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def add_documents(texts, metadatas, ids=None):
    if ids is None:
        ids = [f"doc_{uuid.uuid4().hex}" for _ in range(len(texts))]
    collection.add(documents=texts, metadatas=[_clean_metadata(item) for item in metadatas], ids=ids)


def add_memory_entry(
    text: str,
    *,
    kind: str = "general",
    simulation_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    module: Optional[int] = None,
    agent_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    entry_id: Optional[str] = None,
):
    payload = {
        "kind": kind,
        "simulation_id": simulation_id,
        "thread_id": thread_id,
        "module": module,
        "agent_name": agent_name,
        **(metadata or {}),
    }
    add_documents([text], [payload], ids=[entry_id or f"mem_{uuid.uuid4().hex}"])


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


def query_memory(
    query: str,
    *,
    kind: Optional[str] = None,
    simulation_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    module: Optional[int] = None,
    n_results: int = 3,
):
    where: dict[str, Any] = {}
    if kind:
        where["kind"] = kind
    if simulation_id:
        where["simulation_id"] = simulation_id
    if thread_id:
        where["thread_id"] = thread_id
    if module is not None:
        where["module"] = module

    try:
        if where:
            result = collection.query(query_texts=[query], n_results=n_results, where=where)
        else:
            result = collection.query(query_texts=[query], n_results=n_results)
    except Exception:
        return []

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    return list(zip(documents, metadatas))


def recall_recent_memory(
    *,
    kind: Optional[str] = None,
    simulation_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    module: Optional[int] = None,
    limit: int = 5,
):
    where: dict[str, Any] = {}
    if kind:
        where["kind"] = kind
    if simulation_id:
        where["simulation_id"] = simulation_id
    if thread_id:
        where["thread_id"] = thread_id
    if module is not None:
        where["module"] = module

    try:
        if where:
            result = collection.get(where=where, limit=limit)
        else:
            result = collection.get(limit=limit)
    except Exception:
        return []

    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return list(zip(documents, metadatas))