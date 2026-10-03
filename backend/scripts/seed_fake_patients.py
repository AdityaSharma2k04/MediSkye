import argparse
import asyncio
from datetime import date
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, Document, Chat, ChatChunk, PatientFact, AuditLog
from app.core.auth import get_password_hash

PATIENT_DATA = [
    {
        "first_name": "Aarav", "last_name": "Mehta",
        "dob": date(1985, 4, 12), "sex": "Male", "blood_type": "O+",
        "height": 175, "diet": "vegetarian", "activity": "active",
        "occupation": "Software Engineer", "conditions": "Hypertension",
        "medications": "Amlodipine 5mg", "allergies": "Peanuts",
        "reports": ["Lipid Panel", "CBC", "Metabolic Panel"],
        "critical": False,
        "dependents": [
            {"name": "Ananya Mehta", "rel": "Spouse", "dob": date(1987, 8, 20), "sex": "Female", "blood": "B+"}
        ]
    },
    {
        "first_name": "Priya", "last_name": "Sharma",
        "dob": date(1972, 9, 30), "sex": "Female", "blood_type": "A+",
        "height": 160, "diet": "non_vegetarian", "activity": "sedentary",
        "occupation": "Bank Manager", "conditions": "Type 2 Diabetes, Hypertension, CKD",
        "medications": "Metformin 500mg, Lisinopril 10mg", "allergies": "Penicillin",
        "reports": ["HbA1c", "Kidney Function", "Urinalysis"],
        "critical": True,
        "dependents": []
    },
    {
        "first_name": "Rohan", "last_name": "Iyer",
        "dob": date(1992, 11, 5), "sex": "Male", "blood_type": "B+",
        "height": 180, "diet": "vegan", "activity": "very_active",
        "occupation": "Graphic Designer", "conditions": "Asthma",
        "medications": "Albuterol inhaler PRN", "allergies": "None",
        "reports": ["CBC", "Vitamin D", "Chest X-Ray"],
        "critical": False,
        "dependents": []
    },
    {
        "first_name": "Ananya", "last_name": "Reddy",
        "dob": date(1995, 2, 18), "sex": "Female", "blood_type": "O-",
        "height": 165, "diet": "eggetarian", "activity": "moderate",
        "occupation": "Student", "conditions": "PCOS",
        "medications": "Metformin 500mg", "allergies": "None",
        "reports": ["Thyroid Panel", "Pelvic Ultrasound"],
        "critical": False,
        "dependents": [
            {"name": "Maya Reddy", "rel": "Child", "dob": date(2020, 1, 1), "sex": "Female", "blood": "O-"}
        ]
    },
    {
        "first_name": "Vikram", "last_name": "Singh",
        "dob": date(1965, 7, 22), "sex": "Male", "blood_type": "AB+",
        "height": 170, "diet": "non_vegetarian", "activity": "light",
        "occupation": "Retired", "conditions": "Fatty Liver, Hypertension",
        "medications": "Atorvastatin 20mg", "allergies": "Shellfish",
        "reports": ["LFT", "Lipid Panel", "Abdominal Ultrasound"],
        "critical": False,
        "dependents": [
            {"name": "Sita Singh", "rel": "Spouse", "dob": date(1968, 5, 15), "sex": "Female", "blood": "O+"}
        ]
    },
    {
        "first_name": "Neha", "last_name": "Kapoor",
        "dob": date(1988, 12, 10), "sex": "Female", "blood_type": "A-",
        "height": 158, "diet": "vegetarian", "activity": "active",
        "occupation": "Teacher", "conditions": "Hypothyroidism",
        "medications": "Levothyroxine 50mcg", "allergies": "Sulfa",
        "reports": ["Thyroid Panel", "Vitamin B12", "Iron Panel"],
        "critical": False,
        "dependents": []
    },
    {
        "first_name": "Arjun", "last_name": "Nair",
        "dob": date(1955, 3, 28), "sex": "Male", "blood_type": "B-",
        "height": 168, "diet": "non_vegetarian", "activity": "sedentary",
        "occupation": "Accountant", "conditions": "Type 2 Diabetes, High Cholesterol",
        "medications": "Glipizide 5mg, Rosuvastatin 10mg", "allergies": "None",
        "reports": ["HbA1c", "Lipid Panel", "CMP"],
        "critical": False,
        "dependents": []
    },
    {
        "first_name": "Diya", "last_name": "Bose",
        "dob": date(2000, 6, 14), "sex": "Female", "blood_type": "O+",
        "height": 162, "diet": "vegan", "activity": "moderate",
        "occupation": "Software Intern", "conditions": "None",
        "medications": "None", "allergies": "None",
        "reports": ["CBC", "Vitamin D", "BMP"], # All normal
        "critical": False,
        "dependents": []
    },
    {
        "first_name": "Kabir", "last_name": "Malhotra",
        "dob": date(1980, 1, 9), "sex": "Male", "blood_type": "AB-",
        "height": 178, "diet": "non_vegetarian", "activity": "light",
        "occupation": "Sales Manager", "conditions": "Hypertension",
        "medications": "Losartan 50mg", "allergies": "Penicillin",
        "reports": ["Lipid Panel", "ECG", "Stress Test"],
        "critical": False,
        "dependents": []
    },
    {
        "first_name": "Meera", "last_name": "Joshi",
        "dob": date(1978, 10, 31), "sex": "Female", "blood_type": "A+",
        "height": 164, "diet": "vegetarian", "activity": "moderate",
        "occupation": "Architect", "conditions": "Migraine",
        "medications": "Sumatriptan 50mg PRN", "allergies": "None",
        "reports": ["Vitamin D", "MRI Brain", "CBC"],
        "critical": False,
        "dependents": []
    },
]


async def seed_data(count: int):
    async with AsyncSessionLocal() as session:
        # Delete existing users with @example.com
        result = await session.execute(select(User).where(User.email.like("%@example.com")))
        existing_users = result.scalars().all()
        for u in existing_users:
            await session.delete(u)
        await session.commit()

        password_hash = get_password_hash("TestPatient123!")

        to_create = PATIENT_DATA[:count]
        
        for i, pdata in enumerate(to_create):
            print(f"Creating patient {i+1}/{len(to_create)}: {pdata['first_name']} {pdata['last_name']}...")
            
            email = f"{pdata['first_name'].lower()}.{pdata['last_name'].lower()}@example.com"
            user = User(
                email=email,
                hashed_password=password_hash,
                full_name=f"{pdata['first_name']} {pdata['last_name']}",
                date_of_birth=pdata['dob'],
                biological_sex=pdata['sex'],
                blood_type=pdata['blood_type'],
                pre_existing_conditions=pdata['conditions'],
                known_allergies=pdata['allergies'],
                current_medications=pdata['medications'],
                emergency_contact_name="Emergency Contact",
                emergency_contact_phone="555-0199",
                phi_consent_granted=True,
                memory_consent_granted=True,
                height_cm=pdata['height'],
                diet_type=pdata['diet'],
                activity_level=pdata['activity'],
                occupation=pdata['occupation'],
            )
            session.add(user)
            await session.flush()
            
            # Dependents
            for dep in pdata['dependents']:
                d = DependentProfile(
                    user_id=user.id,
                    relationship=dep['rel'],
                    full_name=dep['name'],
                    date_of_birth=dep['dob'],
                    biological_sex=dep['sex'],
                    blood_type=dep['blood'],
                )
                session.add(d)

            # Fact 3 (Profile fact)
            session.add(PatientFact(
                user_id=user.id,
                fact_type="medication",
                fact_text=f"Patient is taking {pdata['medications']}",
                source_type="profile"
            ))

            # Documents & Facts
            for j, report_name in enumerate(pdata['reports']):
                doc = Document(
                    user_id=user.id,
                    filename=f"{report_name.replace(' ', '_').lower()}.pdf",
                    title=f"{report_name} Result",
                )
                session.add(doc)
                await session.flush()

                # Fact 1
                session.add(PatientFact(
                    user_id=user.id,
                    fact_type="condition",
                    fact_text=f"Report {report_name} indicates review needed" if not pdata['critical'] else "Critical abnormal values found in report",
                    source_type="pdf",
                    source_id=str(doc.id)
                ))
                # Fact 2
                session.add(PatientFact(
                    user_id=user.id,
                    fact_type="measurement",
                    fact_text=f"Blood markers extracted from {report_name}",
                    source_type="pdf",
                    source_id=str(doc.id)
                ))
                
                # Chat & chunks ONLY for the first document to keep Chat count around 15-30
                if j == 0:
                    chat = Chat(
                        user_id=user.id,
                        document_id=doc.id,
                        role="user",
                        message=f"Can you explain my {report_name}?"
                    )
                    session.add(chat)
                    chat_ai = Chat(
                        user_id=user.id,
                        document_id=doc.id,
                        role="ai",
                        message=f"Based on your {report_name}, your levels are {'abnormal' if pdata['critical'] else 'mostly normal'}. You should consult a doctor."
                    )
                    session.add(chat_ai)
                    await session.flush()
                    
                    session.add(ChatChunk(
                        user_id=user.id,
                        chat_id=chat.id,
                        chunk_text=f"User asked about {report_name}"
                    ))

        await session.commit()
        
        # Log counts
        users = await session.execute(select(User))
        deps = await session.execute(select(DependentProfile))
        docs = await session.execute(select(Document))
        facts = await session.execute(select(PatientFact))
        chats = await session.execute(select(Chat))
        
        print(f"\\nFinal counts:")
        print(f"Users: {len(users.scalars().all())}")
        print(f"Dependents: {len(deps.scalars().all())}")
        print(f"Documents: {len(docs.scalars().all())}")
        print(f"PatientFacts: {len(facts.scalars().all())}")
        print(f"Chats: {len(chats.scalars().all())}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10, help="Number of patients to seed")
    args = parser.parse_args()
    
    asyncio.run(seed_data(args.count))
