"""Import stories, legacy JSON, custom text and files through the same service."""

import hashlib
import json
from pathlib import Path

from flask import g, request
from werkzeug.exceptions import NotFound

from .documents import extract_upload
from .web import get_service


def export_sources(owner, root, normalize, index):
    """Compatibility exports contain only currently active source documents."""
    folder = Path(root) / owner
    folder.mkdir(parents=True, exist_ok=True)
    documents = get_service().store.documents(owner)
    combined = {"domains": []}
    for doc in documents:
        selected = doc["metadata"].get("taxonomy", {})
        combined["domains"].extend(normalize(doc["text"], selected)["domains"])
    for filename, value in (("experiences.json", combined), ("chunks_index.json", index(combined))):
        temporary = folder / (filename + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(folder / filename)
    story = next((doc for doc in documents if doc["document_id"] == "story"), None)
    if story:
        (folder / "experiences.md").write_text(story["text"], encoding="utf-8")
        (folder / "selected_items.json").write_text(json.dumps(story["metadata"].get("taxonomy", {})), encoding="utf-8")
    else:
        (folder / "experiences.md").unlink(missing_ok=True)
        (folder / "selected_items.json").unlink(missing_ok=True)


def import_story(data, root, normalize, index):
    owner = g.knowledge_owner
    selected = data.get("selected_items") or {"topics": data.get("selected_topics", [])}
    if not isinstance(selected, dict) or any(not isinstance(value, list) for value in selected.values()):
        raise ValueError("Selected topics must be lists in a JSON object.")
    if "experience_story" in data:
        story = data["experience_story"]
        if not isinstance(story, str):
            raise ValueError("Please paste your experience story.")
    else:
        legacy = data.get("experiences_json")
        try:
            legacy = json.loads(legacy) if isinstance(legacy, str) else legacy
            if not isinstance(legacy, dict):
                raise ValueError()
            parts = []
            for chunk in index(legacy):
                body = [chunk["experience"], chunk.get("unique_angle", "")]
                body.extend(f"{item.get('subtopic', '')}: {item.get('experience', '')}"
                            for item in chunk.get("subtopics", []) if isinstance(item, dict))
                parts.append("## " + chunk["topic"] + "\n" + "\n\n".join(value for value in body if value))
            story = "\n\n".join(parts)
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Please provide a story or a valid legacy experiences JSON object.") from None
    
    # Try to ingest with embeddings, fall back to lexical-only if it fails
    result = None
    try:
        result = get_service().ingest(owner, "story", story, "Experience story", "story", {"taxonomy": selected})
    except Exception as e:
        import logging
        error_str = str(e)
        logging.error(f"Indexing failed: {e}")
        
        # Handle reindex requirement by clearing old data and retrying
        if "Reindex" in error_str or "Embedding configuration changed" in error_str:
            logging.warning("Configuration changed, clearing old index and retrying...")
            try:
                # Clear the old index
                service = get_service()
                for doc in service.store.documents(owner):
                    service.delete_document(owner, doc["document_id"])
                # Try again with fresh start
                result = get_service().ingest(owner, "story", story, "Experience story", "story", {"taxonomy": selected})
            except Exception as retry_error:
                logging.error(f"Retry after clear failed: {retry_error}")
                # Last resort: try without embeddings
                logging.warning("Disabling embeddings and using keyword-only mode")
                original_provider = get_service().provider
                get_service().provider = None
                try:
                    result = get_service().ingest(owner, "story", story, "Experience story", "story", {"taxonomy": selected})
                finally:
                    get_service().provider = original_provider
        # Handle embedding API failures by disabling embeddings temporarily
        elif "timeout" in error_str.lower() or "API" in error_str or "embedding" in error_str.lower():
            logging.warning("Embedding API issue, using keyword-only mode")
            original_provider = get_service().provider
            get_service().provider = None
            try:
                result = get_service().ingest(owner, "story", story, "Experience story", "story", {"taxonomy": selected})
            finally:
                get_service().provider = original_provider
        else:
            raise
    
    export_sources(owner, root, normalize, index)
    return {"ok": True, "session_id": owner, "indexed_count": get_service().status(owner)["chunks_count"],
            "sample_topics": [chunk["source"]["section"] for chunk in get_service().store.chunks(owner).values()][:5],
            "indexing_mode": result["mode"], "warnings": result["warnings"]}


def import_additional(data, root, normalize, index, files=False):
    owner = g.knowledge_owner
    documents = []
    text = data.get("custom_experience", "")
    title = str(data.get("topic_tag") or "Unique Experience")[:300]
    if not isinstance(text, str):
        raise ValueError("Custom experience must be text.")
    if text.strip():
        documents.append({"document_id": "custom_" + hashlib.sha256(title.encode()).hexdigest()[:24],
                          "text": text, "title": title, "source_type": "custom_text"})
    if files:
        documents.extend(extract_upload(upload) for upload in request.files.getlist("files") if upload.filename)
        if not documents:
            raise ValueError("Please select a file containing text.")
        replacement = data.get("replace_document_id")
        if replacement:
            if len(documents) != 1:
                raise ValueError("To replace a source, upload exactly one file without additional custom text.")
            if not any(doc["document_id"] == replacement for doc in get_service().documents(owner)):
                raise NotFound("The source to replace does not belong to this avatar.")
            documents[0]["document_id"] = replacement
        # Selecting the identical file twice does not create duplicate source records.
        documents = list({doc["document_id"]: doc for doc in documents}.values())
    get_service().ingest_many(owner, documents)
    export_sources(owner, root, normalize, index)
    return {"ok": True, "session_id": owner, "message": "Sources saved and indexed." if documents else "Continuing to playground.",
            "indexed_count": get_service().status(owner)["chunks_count"],
            "indexing_mode": "hybrid" if get_service().provider else "lexical",
            "warnings": get_service().status(owner)["warnings"]}
