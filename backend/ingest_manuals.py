import asyncio
import os
import pdfplumber
import json
from datetime import datetime
import uuid

# Config
DB_PROVIDER = os.environ.get("DB_PROVIDER", "memory")
UPLOADS_DIR = "/app/backend/uploads"
KB_FILE = os.path.join(UPLOADS_DIR, "knowledge_documents.json")


async def ingest_manuals():
    manuals_dir = os.path.join(UPLOADS_DIR, "manuals")
    if not os.path.exists(manuals_dir):
        print(f"❌ Manuals directory not found: {manuals_dir}")
        return

    files = [f for f in os.listdir(manuals_dir) if f.endswith(".pdf")]
    print(f"📂 Found {len(files)} manuals to ingest...")

    # Load existing docs if any
    existing_docs = []
    if os.path.exists(KB_FILE):
        try:
            with open(KB_FILE, "r", encoding="utf-8") as f:
                existing_docs = json.load(f)
        except Exception:
            existing_docs = []

    new_docs = []

    for fname in files:
        path = os.path.join(manuals_dir, fname)
        print(f"📖 Processing {fname}...")

        # Check if already ingested (simple check by filename in existing docs)
        if any(d.get("filename") == fname for d in existing_docs):
            print("   ⚠️ Already ingested. Skipping.")
            continue

        try:
            with pdfplumber.open(path) as pdf:
                total_pages = len(pdf.pages)
                print(f"   📄 Total pages: {total_pages}")

                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if not text:
                        continue

                    # Create document chunk
                    doc = {
                        "id": str(uuid.uuid4()),
                        "title": f"{fname} - Page {i+1}",
                        "filename": fname,
                        "page_number": i + 1,
                        "content": text,
                        "type": "manual",
                        "tags": ["manual", "toyota", "repair", fname],
                        "createdAt": datetime.utcnow().isoformat(),
                    }
                    new_docs.append(doc)

                    if len(new_docs) % 50 == 0:
                        print(f"   ... processed {len(new_docs)} pages so far")

            print(f"✅ Finished {fname}")

        except Exception as e:
            print(f"❌ Error processing {fname}: {e}")

    if new_docs:
        all_docs = existing_docs + new_docs
        with open(KB_FILE, "w", encoding="utf-8") as f:
            json.dump(all_docs, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved {len(new_docs)} new pages to {KB_FILE}")
    else:
        print("No new documents to save.")

    print("🎉 Ingestion complete!")


if __name__ == "__main__":
    asyncio.run(ingest_manuals())
