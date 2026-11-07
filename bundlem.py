import os
from pathlib import Path

# The specific missing files Claude asked for
MISSING_FILES = [
    "backend/app/rag/safety.py",
    "backend/app/rag/output_filter.py",
    "backend/app/core/audit.py",
    "backend/app/core/redis_client.py",
    "backend/app/services/pdf_service.py",
    # Add any files inside the middleware folder
    "backend/app/middleware/body_limit.py",
    "backend/app/middleware/security.py",
    "backend/app/middleware/logging.py",
    # Extra safety: metrics and user endpoints
    "backend/app/api/v1/endpoints/metrics.py",
    "backend/app/api/v1/endpoints/user.py",
    "backend/app/rag/retriever.py",
    "backend/app/rag/loader.py",
    "backend/app/services/patient_memory.py",
    "backend/app/services/fact_persistence.py"
]

def bundle_missing():
    output_dir = Path("claude_audit")
    output_dir.mkdir(exist_ok=True)
    
    bundle_path = output_dir / "15_missing_core_files.txt"
    bundle_content = ["===== BUNDLE: Missing Core Files =====\n"]
    
    found_count = 0
    print("Bundling missing files...")
    
    for fp in MISSING_FILES:
        path = Path(fp)
        if path.exists() and path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    code = f.read()
                    bundle_content.append(f"\n\n### FILE: {fp}\n```python\n{code}\n```\n")
                    found_count += 1
                    print(f"✅ Added {fp}")
            except Exception as e:
                pass
                
    if found_count > 0:
        with open(bundle_path, "w", encoding="utf-8") as f:
            f.write("".join(bundle_content))
        print(f"\n🎉 Created {bundle_path} with {found_count} files!")
    else:
        print("\n⚠️ Could not find any of the missing files. Check paths.")

if __name__ == "__main__":
    bundle_missing()