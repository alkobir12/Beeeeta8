"""
Toyota Manual Content API
Serves manual content without iframe
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter(prefix="/api/toyota-manual")

# Load extracted content
CONTENT_DIR = Path(__file__).parent / "static" / "toyota_content"

# Cache for performance
_sections_cache = None
_content_cache = {}
_index_cache = None


def load_sections():
    """Load sections with caching"""
    global _sections_cache
    if _sections_cache is None:
        try:
            with open(CONTENT_DIR / "sections.json", "r", encoding="utf-8") as f:
                _sections_cache = json.load(f)
        except Exception:
            _sections_cache = []
    return _sections_cache


def load_content_batch(batch_num):
    """Load content batch with caching"""
    global _content_cache
    if batch_num not in _content_cache:
        try:
            with open(
                CONTENT_DIR / f"content_batch_{batch_num}.json", "r", encoding="utf-8"
            ) as f:
                _content_cache[batch_num] = json.load(f)
        except Exception:
            _content_cache[batch_num] = []
    return _content_cache[batch_num]


def load_search_index():
    """Load search index"""
    global _index_cache
    if _index_cache is None:
        try:
            with open(CONTENT_DIR / "search_index.json", "r", encoding="utf-8") as f:
                _index_cache = json.load(f)
        except Exception:
            _index_cache = []
    return _index_cache


@router.get("/sections")
async def get_sections():
    """Get all manual sections"""
    sections = load_sections()
    return {"sections": sections, "count": len(sections)}


@router.get("/content")
async def get_all_content(limit: int = 100, offset: int = 0):
    """Get paginated content"""
    # Load all batches
    all_content = []
    for i in range(1, 4):  # 3 batches
        all_content.extend(load_content_batch(i))

    # Paginate
    paginated = all_content[offset : offset + limit]

    return {
        "content": paginated,
        "total": len(all_content),
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(all_content),
    }


@router.get("/content/by-file")
async def get_content_by_file(file: str):
    """Get a single document by its file path"""
    # Load all batches and search for the document
    for i in range(1, 4):
        batch = load_content_batch(i)
        for doc in batch:
            if doc.get("file") == file:
                return {"doc": doc}
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/search")
async def search_manual(q: str, limit: int = 50):
    """Search in manual content with better error handling"""
    try:
        if not q or len(q.strip()) < 1:
            return {"results": [], "count": 0, "query": q}

        index = load_search_index()
        query = q.strip().lower()

        results = []
        for entry in index:
            # Safe search in title and preview
            title = (entry.get("title") or "").lower()
            preview = (entry.get("preview") or "").lower()

            if query in title or query in preview:
                results.append(entry)
                if len(results) >= limit:
                    break

        return {"results": results, "count": len(results), "query": q}
    except Exception as e:
        print(f"Search error: {e}")
        return {"results": [], "count": 0, "query": q, "error": str(e)}


@router.get("/section/{section_id}/content")
async def get_section_content(section_id: str, limit: int = 50):
    """Get content for a specific section"""
    # Map section IDs to content
    # This is simplified - in production, you'd have better mapping
    all_content = []
    for i in range(1, 4):
        all_content.extend(load_content_batch(i))

    # Filter by section (basic filtering for now)
    # You can enhance this by mapping files to sections
    filtered = all_content[:limit]

    return {"section_id": section_id, "content": filtered, "count": len(filtered)}


@router.get("/stats")
async def get_stats():
    """Get manual statistics"""
    sections = load_sections()
    index = load_search_index()

    # Count images
    total_images = 0
    for i in range(1, 4):
        batch = load_content_batch(i)
        total_images += sum(len(doc.get("images", [])) for doc in batch)

    return {
        "sections": len(sections),
        "documents": len(index),
        "images": total_images,
        "total_pages": 15644,
        "extracted_pages": len(index),
    }
