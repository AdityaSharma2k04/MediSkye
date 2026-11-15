import sys, os, json, asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.db.models import Document, User
from sqlalchemy.future import select
from app.api.v1.endpoints.metrics import _apply_longitudinal_deltas
from scripts.run_full_e2e_clinical_test import build_markdown_report

async def sync():
    checkpoint_path = backend_dir / "scripts" / "e2e_checkpoint.json"
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).filter(User.email == "mediskye@test.com"))
        user = res.scalars().first()

        doc_res = await db.execute(select(Document).filter(Document.user_id == user.id))
        docs = {str(d.id): d for d in doc_res.scalars().all()}

        for s_key, s_data in data["sessions"].items():
            doc_id = s_data.get("document_id")
            if not doc_id or doc_id not in docs:
                continue

            doc_item = docs[doc_id]
            cached_raw = doc_item.cached_metrics
            if isinstance(cached_raw, str):
                try:
                    cached_raw = json.loads(cached_raw)
                except Exception:
                    cached_raw = []
            if isinstance(cached_raw, dict) and "metrics" in cached_raw:
                cached_raw = cached_raw["metrics"]
            if not isinstance(cached_raw, list):
                cached_raw = []

            metric_items, prior_id, prior_date = await _apply_longitudinal_deltas(
                doc_item, cached_raw, user, db
            )

            metrics_list = []
            for m in metric_items:
                metrics_list.append({
                    "test": m.test,
                    "value": m.value,
                    "unit": m.unit,
                    "range": m.range,
                    "status": m.status,
                    "previous_value": m.previous_value,
                    "previous_date": m.previous_date,
                    "delta_abs": m.delta_abs,
                    "delta_pct": m.delta_pct,
                    "delta_alert": m.delta_alert,
                })

            s_data["metrics"] = metrics_list
            print(f"Updated {s_key} (doc_id={doc_id}) with {len(metrics_list)} metrics.")

    # Save updated checkpoint
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Saved updated e2e_checkpoint.json.")

    # Build prompt_and_answers.md
    md_content = build_markdown_report(data)
    out_path = backend_dir.parent / "prompt_and_answers.md"
    out_path.write_text(md_content, encoding="utf-8")
    print(f"Successfully generated {out_path} ({len(md_content)} chars, {out_path.stat().st_size} bytes).")

if __name__ == "__main__":
    asyncio.run(sync())
