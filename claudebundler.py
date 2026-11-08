"""
Bundles the entire MediSkye codebase (Frontend + Backend + Configs) into 15 .txt files
inside ./claude_bundles/ so they can be uploaded to Free Claude (20-file limit) in one go.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "claude_bundles"

SKIP_DIRS = {
    "node_modules", ".venv", "venv", "dist", "build", "__pycache__",
    ".git", ".pytest_cache", ".vector_cache", "coverage", "claude_bundles",
    "assets", "screenshots",
}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".DS_Store", "testing_log"}
ALLOWED_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".json", ".html", ".ini", ".txt", ".yaml", ".yml"}


def collect_files(base_dir: Path, predicate=None) -> list[Path]:
    matched = []
    if not base_dir.exists():
        return matched
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f in SKIP_FILES or f.startswith(".env"):
                continue
            p = Path(root) / f
            if p.suffix.lower() not in ALLOWED_EXTS:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if predicate is None or predicate(rel):
                matched.append(p)
    return matched


def write_bundle(filename: str, paths: list[Path], seen: set[Path]):
    OUT_DIR.mkdir(exist_ok=True)
    unique_paths = [p for p in paths if p.exists() and p not in seen]
    for p in unique_paths:
        seen.add(p)

    out_path = OUT_DIR / filename
    lines = [
        f"===== BUNDLE: {filename} ({len(unique_paths)} files) =====",
        "Included files:",
        *[f"  - {p.relative_to(ROOT).as_posix()}" for p in unique_paths],
        "\n" + "=" * 70 + "\n",
    ]
    for p in unique_paths:
        rel = p.relative_to(ROOT).as_posix()
        ext = p.suffix.lstrip(".") or "txt"
        content = p.read_text(encoding="utf-8", errors="replace")
        lines.append(f"### FILE: {rel}\n```{ext}\n{content}\n```\n\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"  [OK] {filename:<34} | {len(unique_paths):>2} files | {size_kb:>6.1f} KB")


def main():
    seen: set[Path] = set()
    print("Generating 15 complete bundles in ./claude_bundles/ ...")

    # ── FRONTEND (Bundles 01 to 07) ──
    write_bundle("01_fe_app_core_and_styles.txt", collect_files(
        ROOT / "frontend",
        lambda r: any(r.endswith(x) for x in ("index.html", "package.json", "vite.config.js", "tailwind.config.js", "vitest.config.js"))
        or (r.startswith("frontend/src/") and r.count("/") == 2)
        or r.startswith("frontend/src/styles/")
        or r.startswith("frontend/src/lib/")
    ), seen)

    write_bundle("02_fe_hooks_and_services.txt", collect_files(
        ROOT / "frontend/src",
        lambda r: "/hooks/" in r or "/services/" in r or "/locales/" in r
    ), seen)

    write_bundle("03_fe_chat_and_main_container.txt", collect_files(
        ROOT / "frontend/src/components",
        lambda r: any(k in r for k in ("ChatApp", "ChatWindow", "ChatInput", "ChatMessage", "Sidebar"))
    ), seen)

    write_bundle("04_fe_workbench_and_ui_primitives.txt", collect_files(
        ROOT / "frontend/src/components",
        lambda r: "/workbench/" in r or "/ui/" in r
    ), seen)

    write_bundle("05_fe_clinical_and_print_views.txt", collect_files(
        ROOT / "frontend/src/components",
        lambda r: "/clinical/" in r or any(k in r for k in ("LabMetrics", "PrintableSummary", "PrintableTranscript", "ExportModal"))
    ), seen)

    write_bundle("06_fe_auth_settings_profile_landing.txt", collect_files(
        ROOT / "frontend/src/components",
        lambda r: True  # catches all remaining components (Auth, Settings, Profile, Landing, Modals)
    ), seen)

    write_bundle("07_fe_vitest_suite.txt", collect_files(
        ROOT / "frontend/src/test"
    ), seen)

    # ── BACKEND (Bundles 08 to 15) ──
    write_bundle("08_be_main_core_and_middleware.txt", collect_files(
        ROOT / "backend/app",
        lambda r: r.endswith("main.py") or "/core/" in r or "/middleware/" in r or r.endswith("router.py")
    ), seen)

    write_bundle("09_be_db_models_and_schemas.txt", collect_files(
        ROOT / "backend",
        lambda r: "/db/" in r or "/schemas/" in r or "/alembic/" in r
    ), seen)

    write_bundle("10_be_endpoints_auth_and_query.txt", collect_files(
        ROOT / "backend/app/api",
        lambda r: any(r.endswith(x) for x in ("auth.py", "query.py", "chat.py", "health.py"))
    ), seen)

    write_bundle("11_be_endpoints_user_upload_metrics.txt", collect_files(
        ROOT / "backend/app/api",
        lambda r: True  # catches user.py, upload.py, metrics.py, and any remaining endpoints
    ), seen)

    write_bundle("12_be_rag_pipeline_and_prompts.txt", collect_files(
        ROOT / "backend/app/rag"
    ), seen)

    write_bundle("13_be_services_and_llm_client.txt", collect_files(
        ROOT / "backend/app",
        lambda r: "/services/" in r or "/llm/" in r or True  # catches all remaining backend/app files
    ), seen)

    write_bundle("14_be_pytest_suite_part1.txt", collect_files(
        ROOT / "backend/tests",
        lambda r: Path(r).name <= "test_m"
    ), seen)

    write_bundle("15_be_pytest_suite_part2_and_configs.txt", (
        collect_files(ROOT / "backend/tests")
        + collect_files(ROOT / "backend", lambda r: r.count("/") == 1)
        + [ROOT / "README.md", ROOT / "cloudbuild.yaml"]
    ), seen)

    print(f"\nDone! Total unique source files packed: {len(seen)} across 15 bundles in ./claude_bundles/")


if __name__ == "__main__":
    main()