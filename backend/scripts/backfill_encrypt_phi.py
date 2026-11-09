"""
Encrypt (or revert) legacy plaintext PHI columns.

From backend/:
  python scripts/backfill_encrypt_phi.py                                    # dry run: counts only, changes nothing
  python scripts/backfill_encrypt_phi.py --apply --confirm-backup           # encrypt
  python scripts/backfill_encrypt_phi.py --revert --apply --confirm-backup  # emergency rollback to plaintext

FERNET_KEY must be the SAME key the production service uses. Take a database backup/branch first.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import AsyncSessionLocal, engine  # noqa: E402
from app.services.phi_backfill import preflight_column_limits, preflight_key_matches, run_backfill  # noqa: E402


async def main(args) -> int:
    url = make_url(str(settings.DATABASE_URL))
    print(f"Database: {url.drivername} host={url.host} db={url.database}")
    print(f"Mode: {'REVERT' if args.revert else 'ENCRYPT'} | {'APPLY' if args.apply else 'DRY RUN'}")
    is_sqlite = engine.dialect.name == "sqlite"
    if args.apply and not is_sqlite and not args.confirm_backup:
        print("Refusing to modify a non-SQLite database without --confirm-backup.")
        return 2
    async with AsyncSessionLocal() as session:
        problems = await preflight_column_limits(session, engine.dialect.name)
        key_problem = await preflight_key_matches(session)
        await session.rollback()
        if problems or key_problem:
            for p in problems + ([key_problem] if key_problem else []):
                print("PREFLIGHT FAILED:", p)
            return 2
        stats = await run_backfill(session, mode="revert" if args.revert else "encrypt",
                                   apply=args.apply, batch_size=args.batch_size)
    print(f"{'table.column':34} {'total':>7} {'null':>6} {'enc':>6} {'plain':>6} {'undec':>6} {'updated':>8}")
    for s in stats:
        print(f"{s.label:34} {s.total:>7} {s.null:>6} {s.encrypted:>6} {s.plaintext:>6} {s.undecryptable:>6} {s.updated:>8}")
    await engine.dispose()
    return 3 if any(s.undecryptable for s in stats) else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="actually write changes (default is a dry run)")
    p.add_argument("--revert", action="store_true", help="decrypt back to plaintext (rollback)")
    p.add_argument("--confirm-backup", action="store_true", help="required with --apply on a non-SQLite database")
    p.add_argument("--batch-size", type=int, default=100)
    sys.exit(asyncio.run(main(p.parse_args())))

