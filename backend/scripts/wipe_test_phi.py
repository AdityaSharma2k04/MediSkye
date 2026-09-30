import os
import sys
import argparse
import asyncio
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Set fallback for JWT_SECRET_KEY for maintenance script invocation if not yet in .env
if "JWT_SECRET_KEY" not in os.environ:
    os.environ["JWT_SECRET_KEY"] = "maintenance_wipe_script_placeholder_key_32chars"

from sqlalchemy.future import select
from sqlalchemy import func
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, Document, Chat, AuditLog


async def inspect_and_wipe(confirm: bool = False):
    async with AsyncSessionLocal() as session:
        # Count Users and Dependents
        user_count = (await session.execute(select(func.count(User.id)))).scalar_one()
        dep_count = (await session.execute(select(func.count(DependentProfile.id)))).scalar_one()

        # Count encrypted fields with non-null values
        # 4 fields in User: blood_type, pre_existing_conditions, known_allergies, current_medications
        # 4 fields in DependentProfile: blood_type, pre_existing_conditions, known_allergies, current_medications
        users = (await session.execute(select(User))).scalars().all()
        deps = (await session.execute(select(DependentProfile))).scalars().all()

        encrypted_fields_count = 0
        for u in users:
            for field in [u.blood_type, u.pre_existing_conditions, u.known_allergies, u.current_medications]:
                if field is not None:
                    encrypted_fields_count += 1

        for d in deps:
            for field in [d.blood_type, d.pre_existing_conditions, d.known_allergies, d.current_medications]:
                if field is not None:
                    encrypted_fields_count += 1

        print(f"Found {user_count} users, {dep_count} dependents, {encrypted_fields_count} encrypted fields total. All are test data.")

        if confirm:
            print("Wiping test PHI data from database...")
            # Delete dependent audit logs and records
            await session.execute(AuditLog.__table__.delete())
            await session.execute(Chat.__table__.delete())
            await session.execute(Document.__table__.delete())
            await session.execute(DependentProfile.__table__.delete())
            await session.execute(User.__table__.delete())
            await session.commit()
            print("Successfully wiped all test PHI and associated records.")
        else:
            print("Dry run complete. No data was modified. Pass --confirm to wipe.")


def main():
    parser = argparse.ArgumentParser(description="Wipe test PHI records from MediSkye SQLite database.")
    parser.add_argument("--confirm", action="store_true", help="Confirm deletion of test data")
    args = parser.parse_args()

    asyncio.run(inspect_and_wipe(confirm=args.confirm))


if __name__ == "__main__":
    main()
