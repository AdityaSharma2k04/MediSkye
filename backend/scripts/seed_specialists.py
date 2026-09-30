import asyncio
import json
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.models import Specialist, Base
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SPECIALISTS = [
    {
        "name": "Dr. Sarah Chen",
        "specialty": "Cardiology",
        "keywords": ["Troponin", "CK-MB", "BNP", "Lipid Panel", "Cholesterol", "Triglycerides", "ECG", "Echocardiogram"],
        "contact_info": "sarah.chen@mediskye.org | 555-0101"
    },
    {
        "name": "Dr. Marcus Johnson",
        "specialty": "Cardiology",
        "keywords": ["Troponin", "BNP", "Blood Pressure", "Heart Rate", "Arrhythmia"],
        "contact_info": "marcus.j@mediskye.org | 555-0102"
    },
    {
        "name": "Dr. Emily Patel",
        "specialty": "Cardiology",
        "keywords": ["Cholesterol", "LDL", "HDL", "Apolipoprotein", "Lipid"],
        "contact_info": "emily.patel@mediskye.org | 555-0103"
    },
    {
        "name": "Dr. Michael Chang",
        "specialty": "Endocrinology",
        "keywords": ["HbA1c", "Glucose", "Fasting Blood Sugar", "Thyroid", "TSH", "T3", "T4", "Insulin", "Cortisol"],
        "contact_info": "m.chang@mediskye.org | 555-0201"
    },
    {
        "name": "Dr. Rachel Green",
        "specialty": "Endocrinology",
        "keywords": ["HbA1c", "Diabetes", "Thyroid", "Hormone", "Testosterone", "Estrogen"],
        "contact_info": "rachel.g@mediskye.org | 555-0202"
    },
    {
        "name": "Dr. David Smith",
        "specialty": "Endocrinology",
        "keywords": ["Glucose", "Vitamin D", "Calcium", "PTH", "Bone Density"],
        "contact_info": "d.smith@mediskye.org | 555-0203"
    },
    {
        "name": "Dr. Elena Rodriguez",
        "specialty": "Nephrology",
        "keywords": ["Creatinine", "BUN", "eGFR", "Urea", "Proteinuria", "Urinalysis", "Sodium", "Potassium"],
        "contact_info": "elena.r@mediskye.org | 555-0301"
    },
    {
        "name": "Dr. James Wilson",
        "specialty": "Nephrology",
        "keywords": ["eGFR", "Kidney", "Microalbumin", "Uric Acid", "Electrolytes"],
        "contact_info": "j.wilson@mediskye.org | 555-0302"
    },
    {
        "name": "Dr. Lisa Cuddy",
        "specialty": "Nephrology",
        "keywords": ["Creatinine", "BUN", "Kidney Stone", "Hematuria"],
        "contact_info": "l.cuddy@mediskye.org | 555-0303"
    },
    {
        "name": "Dr. Robert Chase",
        "specialty": "Hematology",
        "keywords": ["CBC", "Hemoglobin", "Hematocrit", "Platelets", "WBC", "RBC", "Ferritin", "Iron", "B12"],
        "contact_info": "r.chase@mediskye.org | 555-0401"
    },
    {
        "name": "Dr. Allison Cameron",
        "specialty": "Hematology",
        "keywords": ["Leukocytes", "Neutrophils", "Lymphocytes", "Coagulation", "PT", "INR", "aPTT"],
        "contact_info": "a.cameron@mediskye.org | 555-0402"
    },
    {
        "name": "Dr. Eric Foreman",
        "specialty": "Hematology",
        "keywords": ["Anemia", "Hemoglobin", "Iron", "TIBC", "Transferrin"],
        "contact_info": "e.foreman@mediskye.org | 555-0403"
    },
    {
        "name": "Dr. Gregory House",
        "specialty": "Pathology",
        "keywords": ["Biopsy", "Cytology", "Histology", "Tumor Marker", "PSA", "CEA", "CA-125"],
        "contact_info": "g.house@mediskye.org | 555-0501"
    },
    {
        "name": "Dr. Remy Hadley",
        "specialty": "Pathology",
        "keywords": ["Pathology Report", "Malignancy", "Benign", "Flow Cytometry"],
        "contact_info": "r.hadley@mediskye.org | 555-0502"
    },
    {
        "name": "Dr. Chris Taub",
        "specialty": "Pathology",
        "keywords": ["Genetic Testing", "BRCA", "Molecular Diagnostics", "PCR"],
        "contact_info": "c.taub@mediskye.org | 555-0503"
    }
]

async def seed_data():
    async with AsyncSessionLocal() as session:
        for data in SPECIALISTS:
            specialist = Specialist(
                name=data["name"],
                specialty=data["specialty"],
                keywords=data["keywords"],
                contact_info=data["contact_info"]
            )
            session.add(specialist)
        
        await session.commit()
        print(f"Successfully seeded {len(SPECIALISTS)} specialists.")

if __name__ == "__main__":
    asyncio.run(seed_data())
