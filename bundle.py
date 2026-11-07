import os
from pathlib import Path

# Configuration
IGNORE_DIRS = {'node_modules', '.venv', 'venv', 'dist', '__pycache__', '.git', '.pytest_cache', 'test_reports', 'indexes', '.vector_cache', 'docs', 'public', 'screenshots'}
IGNORE_EXTS = {'.png', '.jpg', '.jpeg', '.pdf', '.map', '.json', '.lock', '.ico', '.svg', '.db', '.sqlite'}

# Define logical groupings (We will bundle into 14 files)
BUNDLES = {
    "01_frontend_core.txt": [
        "frontend/src/App.jsx", "frontend/src/main.jsx", "frontend/src/ChatApp.jsx", 
        "frontend/src/index.css"
    ],
    "02_frontend_chat_ui.txt": [
        "frontend/src/components/ChatWindow.jsx", "frontend/src/components/ChatInput.jsx", 
        "frontend/src/components/ChatMessage.jsx", "frontend/src/components/ui/Markdown.jsx"
    ],
    "03_frontend_clinical_ui.txt": [
        "frontend/src/components/LabMetrics.jsx", "frontend/src/components/workbench/InspectorPanel.jsx", 
        "frontend/src/components/PrintableSummary.jsx", "frontend/src/components/PrintableTranscript.jsx",
        "frontend/src/components/clinical/TrendChart.jsx", "frontend/src/components/clinical/RangeBar.jsx",
        "frontend/src/components/clinical/StatusPill.jsx", "frontend/src/components/clinical/OrganSystemsOverview.jsx",
        "frontend/src/components/clinical/TrendsView.jsx"
    ],
    "04_frontend_workbench_layout.txt": [
        "frontend/src/components/workbench/Workbench.jsx", "frontend/src/components/workbench/NavRail.jsx",
        "frontend/src/components/Sidebar.jsx", "frontend/src/components/workbench/PatientSwitcher.jsx",
        "frontend/src/components/workbench/CommandPalette.jsx", "frontend/src/components/workbench/MemoryVault.jsx",
        "frontend/src/components/workbench/UploadStepper.jsx"
    ],
    "05_frontend_auth_settings.txt": [
        "frontend/src/components/SettingsModal.jsx", "frontend/src/components/Profile.jsx",
        "frontend/src/components/HealthProfile.jsx", "frontend/src/components/Login.jsx",
        "frontend/src/components/Register.jsx", "frontend/src/components/auth/AuthShell.jsx",
        "frontend/src/components/ExportModal.jsx", "frontend/src/components/ConfirmModal.jsx"
    ],
    "06_frontend_hooks_services.txt": [
        "frontend/src/hooks/useLabMetrics.js", "frontend/src/hooks/useTrendData.js",
        "frontend/src/hooks/useChatStream.js", "frontend/src/hooks/useResizablePane.js",
        "frontend/src/hooks/useViewport.js", "frontend/src/services/api.js",
        "frontend/src/services/firebase.js", "frontend/src/lib/clinical.js", 
        "frontend/src/lib/storageKeys.js"
    ],
    "07_backend_main_core.txt": [
        "backend/app/main.py", "backend/app/core/auth.py", "backend/app/core/config.py",
        "backend/app/core/limiter.py", "backend/app/core/observability.py", "backend/app/core/security.py"
    ],
    "08_backend_endpoints_a.txt": [
        "backend/app/api/v1/endpoints/auth.py", "backend/app/api/v1/endpoints/query.py",
        "backend/app/api/v1/endpoints/chat.py"
    ],
    "09_backend_endpoints_b.txt": [
        "backend/app/api/v1/endpoints/user.py", "backend/app/api/v1/endpoints/upload.py",
        "backend/app/api/v1/endpoints/metrics.py"
    ],
    "10_backend_db_models.txt": [
        "backend/app/db/models.py", "backend/app/db/database.py", "backend/app/db/encryption.py"
    ],
    "11_backend_services_llm.txt": [
        "backend/app/services/clinical_units.py", "backend/app/services/patient_memory.py",
        "backend/app/services/fact_persistence.py", "backend/app/services/upload_jobs.py",
        "backend/app/llm/gemini_client.py", "backend/app/llm/embedder.py"
    ],
    "12_backend_rag_prompts.txt": [
        "backend/app/rag/retriever.py", "backend/app/rag/prompt_builder.py",
        "backend/app/rag/intent_router.py", "backend/app/rag/loader.py",
        "backend/app/rag/memory_formatter.py"
    ],
    "13_backend_schemas_tests.txt": [
        "backend/app/schemas/query.py", "backend/app/schemas/user.py",
        "backend/tests/conftest.py", "backend/tests/test_metrics_chronology_and_collision.py",
        "backend/tests/test_audit_fixes.py", "backend/tests/test_sre_hardening.py"
    ],
    "14_configs.txt": [
        "backend/requirements.txt", "backend/alembic.ini", "frontend/package.json",
        "frontend/vite.config.js", "frontend/tailwind.config.js"
    ]
}

def bundle_codebase():
    output_dir = Path("claude_audit")
    output_dir.mkdir(exist_ok=True)
    
    print(f"🚀 Starting bundle process into '{output_dir}/'...")
    
    for bundle_name, filepaths in BUNDLES.items():
        bundle_content = []
        bundle_content.append(f"===== BUNDLE: {bundle_name} =====\n")
        
        for fp in filepaths:
            path = Path(fp)
            if path.exists() and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        code = f.read()
                        bundle_content.append(f"\n\n### FILE: {fp}\n```{path.suffix[1:] if path.suffix else 'text'}\n{code}\n```\n")
                except Exception as e:
                    bundle_content.append(f"\n\n### FILE: {fp}\n[ERROR READING FILE: {e}]\n")
            else:
                bundle_content.append(f"\n\n### FILE: {fp}\n[FILE NOT FOUND]\n")
                
        # Write bundle
        with open(output_dir / bundle_name, "w", encoding="utf-8") as f:
            f.write("".join(bundle_content))
            
        print(f"✅ Created {bundle_name} ({len(filepaths)} files combined)")

    print("\n🎉 Done! You can now upload the 14 files from the 'claude_audit/' folder to Claude.")

if __name__ == "__main__":
    bundle_codebase()