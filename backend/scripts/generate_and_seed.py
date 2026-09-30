import os
import sys
import uuid
import asyncio
from datetime import datetime, date, timezone
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Configure stdout for UTF-8 in Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas

# ─────────────────────────────────────────────────────────────────────────────
# Numbered Canvas for Dynamic "Page X of Y" Footer & Running Headers
# ─────────────────────────────────────────────────────────────────────────────
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer divider line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(40, 42, 555, 42)

        # Footer texts
        left_text = "MediSkye Central Diagnostic Reference Laboratories • ISO 15189:2022 & NABL Accredited"
        center_text = "Electronically Validated Report"
        right_text = f"Page {self._pageNumber} of {page_count}"

        self.drawString(40, 28, left_text)
        self.drawCentredString(360, 28, center_text)
        self.drawRightString(555, 28, right_text)

        self.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# 10 Multi-Panel Medical Reports Data
# ─────────────────────────────────────────────────────────────────────────────
REPORTS_DATA = [
    {
        "id": "MSK-2026-001",
        "filename": "testreport1.pdf",
        "email": "report1@test.com",
        "name": "Rajesh Kumar",
        "age": 52,
        "dob": "14-Mar-1973",
        "dob_date": date(1973, 3, 14),
        "gender": "Male",
        "blood_group": "B+",
        "past_history": "Type 2 Diabetes (2015), Hypertension (2018), Smoker (quit 2020)",
        "allergies": "Penicillin",
        "doctor": "Dr. A. Banerjee, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "13.1", "Normal", "13.0 - 17.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "9,800", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.4", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Hematocrit (PCV)", "40.0", "Normal", "40.0 - 50.0", "%"),
                    ("Mean Corpuscular Volume (MCV)", "86.0", "Normal", "80.0 - 100.0", "fL"),
                    ("Mean Corpuscular Hemoglobin (MCH)", "28.0", "Normal", "27.0 - 33.0", "pg"),
                    ("Neutrophils", "72.0", "Normal", "40.0 - 75.0", "%"),
                ]
            },
            {
                "name": "Diabetes & Glycemic Profile",
                "tests": [
                    ("Fasting Blood Glucose", "168.0", "HIGH", "70.0 - 100.0", "mg/dL"),
                    ("Post-Prandial Blood Glucose", "254.0", "HIGH", "< 140.0", "mg/dL"),
                    ("HbA1c (Glycated Hemoglobin)", "8.4", "HIGH", "< 5.7", "%"),
                    ("Fasting Serum Insulin", "22.0", "HIGH", "2.0 - 19.0", "µIU/mL"),
                    ("Urine Microalbumin / Creatinine Ratio", "68.0", "HIGH", "< 30.0", "mg/g Cr"),
                ]
            },
            {
                "name": "Lipid Profile",
                "tests": [
                    ("Total Cholesterol", "232.0", "HIGH", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol (Calculated)", "148.0", "HIGH", "< 100.0", "mg/dL"),
                    ("HDL Cholesterol", "34.0", "LOW", "> 40.0", "mg/dL"),
                    ("Triglycerides", "218.0", "HIGH", "< 150.0", "mg/dL"),
                    ("VLDL Cholesterol", "44.0", "HIGH", "< 30.0", "mg/dL"),
                ]
            },
            {
                "name": "Liver Function Tests (LFT)",
                "tests": [
                    ("SGPT / ALT", "58.0", "HIGH", "7.0 - 56.0", "U/L"),
                    ("SGOT / AST", "46.0", "HIGH", "10.0 - 40.0", "U/L"),
                    ("Bilirubin Total", "1.10", "Normal", "0.30 - 1.20", "mg/dL"),
                    ("Serum Albumin", "3.90", "Normal", "3.50 - 5.00", "g/dL"),
                    ("Alkaline Phosphatase (ALP)", "112.0", "Normal", "44.0 - 147.0", "U/L"),
                ]
            },
            {
                "name": "Kidney Function Tests (KFT / Renal Profile)",
                "tests": [
                    ("Serum Creatinine", "1.20", "HIGH", "0.60 - 1.10", "mg/dL"),
                    ("Blood Urea Nitrogen (BUN)", "22.0", "HIGH", "7.0 - 20.0", "mg/dL"),
                    ("Estimated GFR (eGFR)", "74.0", "LOW", "> 90.0", "mL/min"),
                    ("Serum Uric Acid", "7.8", "HIGH", "3.4 - 7.0", "mg/dL"),
                    ("Serum Sodium", "138.0", "Normal", "135.0 - 145.0", "mEq/L"),
                    ("Serum Potassium", "4.60", "Normal", "3.50 - 5.00", "mEq/L"),
                ]
            },
            {
                "name": "Thyroid & Micronutrients",
                "tests": [
                    ("TSH (Ultrasensitive)", "3.40", "Normal", "0.40 - 4.00", "µIU/mL"),
                    ("Vitamin D (25-OH)", "19.0", "LOW", "30.0 - 100.0", "ng/mL"),
                    ("Vitamin B12 (Cyanocobalamin)", "310.0", "Normal", "200.0 - 900.0", "pg/mL"),
                ]
            },
            {
                "name": "Routine Urinalysis",
                "tests": [
                    ("Urine Protein", "Trace", "ABNORMAL", "Negative", ""),
                    ("Urine Glucose", "2+", "ABNORMAL", "Negative", ""),
                    ("Urine Ketones", "Negative", "Normal", "Negative", ""),
                    ("Pus Cells / Leukocytes", "4-5", "Normal", "0 - 5", "/hpf"),
                ]
            },
            {
                "name": "Vitals & Electrocardiology",
                "tests": [
                    ("Blood Pressure (Sitting)", "152/96", "HIGH", "90-120 / 60-80", "mmHg"),
                    ("Heart Rate (Resting)", "88", "Normal", "60 - 100", "bpm"),
                    ("Body Mass Index (BMI)", "29.4", "HIGH", "18.5 - 24.9", "kg/m²"),
                    ("12-Lead Resting ECG", "LVH with T-wave inversion V4-V6", "ABNORMAL", "Normal Sinus Rhythm", ""),
                ]
            },
        ],
        "impression": "Poorly controlled T2DM with early diabetic nephropathy, dyslipidemia, hypertension with LVH, Vitamin D deficiency."
    },
    {
        "id": "MSK-2026-002",
        "filename": "testreport2.pdf",
        "email": "report2@test.com",
        "name": "Priya Sharma",
        "age": 34,
        "dob": "22-Jul-1991",
        "dob_date": date(1991, 7, 22),
        "gender": "Female",
        "blood_group": "O+",
        "past_history": "Hypothyroidism (2020), Postpartum 2022",
        "allergies": "None",
        "doctor": "Dr. S. Kulkarni, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "11.2", "LOW", "12.0 - 15.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "6,400", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.7", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Mean Corpuscular Volume (MCV)", "78.0", "LOW", "80.0 - 100.0", "fL"),
                    ("Mean Corpuscular Hemoglobin (MCH)", "25.0", "LOW", "27.0 - 33.0", "pg"),
                    ("ESR (Westergren)", "28.0", "HIGH", "0.0 - 20.0", "mm/hr"),
                ]
            },
            {
                "name": "Thyroid Function & Autoantibody Panel",
                "tests": [
                    ("TSH (Thyroid Stimulating Hormone)", "8.90", "HIGH", "0.40 - 4.00", "µIU/mL"),
                    ("Total Triiodothyronine (T3)", "0.70", "LOW", "0.80 - 2.00", "ng/mL"),
                    ("Total Thyroxine (T4)", "4.10", "LOW", "5.10 - 14.10", "µg/dL"),
                    ("Free Thyroxine (FT4)", "0.70", "LOW", "0.80 - 1.80", "ng/dL"),
                    ("Anti-Thyroid Peroxidase (Anti-TPO)", "340.0", "HIGH", "< 35.0", "IU/mL"),
                ]
            },
            {
                "name": "Iron & Ferritin Studies",
                "tests": [
                    ("Serum Ferritin", "22.0", "LOW", "30.0 - 400.0", "ng/mL"),
                    ("Serum Iron", "48.0", "LOW", "60.0 - 170.0", "µg/dL"),
                    ("Total Iron Binding Capacity (TIBC)", "420.0", "Normal", "250.0 - 450.0", "µg/dL"),
                    ("Transferrin Saturation", "11.4", "LOW", "20.0 - 50.0", "%"),
                ]
            },
            {
                "name": "Vitamins & Micronutrients",
                "tests": [
                    ("Vitamin D (25-OH)", "24.0", "LOW", "30.0 - 100.0", "ng/mL"),
                    ("Vitamin B12", "260.0", "Normal", "200.0 - 900.0", "pg/mL"),
                    ("Serum Folate", "5.20", "Normal", "4.00 - 20.00", "ng/mL"),
                ]
            },
            {
                "name": "Lipid Profile",
                "tests": [
                    ("Total Cholesterol", "198.0", "Normal", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol", "118.0", "HIGH", "< 100.0", "mg/dL"),
                    ("HDL Cholesterol", "46.0", "Normal", "> 40.0", "mg/dL"),
                    ("Serum Triglycerides", "138.0", "Normal", "< 150.0", "mg/dL"),
                ]
            },
            {
                "name": "Liver & Kidney Function",
                "tests": [
                    ("SGPT / ALT", "32.0", "Normal", "7.0 - 56.0", "U/L"),
                    ("SGOT / AST", "28.0", "Normal", "10.0 - 40.0", "U/L"),
                    ("Serum Creatinine", "0.80", "Normal", "0.60 - 1.10", "mg/dL"),
                    ("Serum Blood Urea", "24.0", "Normal", "15.0 - 40.0", "mg/dL"),
                ]
            },
            {
                "name": "Routine Urinalysis",
                "tests": [
                    ("Urine Protein", "Negative", "Normal", "Negative", ""),
                    ("Urine Glucose", "Negative", "Normal", "Negative", ""),
                    ("Pus Cells", "2-3", "Normal", "0 - 5", "/hpf"),
                ]
            },
        ],
        "impression": "Autoimmune primary hypothyroidism with suboptimal control, iron deficiency anemia, Vitamin D insufficiency."
    },
    {
        "id": "MSK-2026-003",
        "filename": "testreport3.pdf",
        "email": "report3@test.com",
        "name": "Arjun Mehta",
        "age": 28,
        "dob": "09-Nov-1997",
        "dob_date": date(1997, 11, 9),
        "gender": "Male",
        "blood_group": "A+",
        "past_history": "Bronchial Asthma (childhood), Allergic rhinitis, Eczema",
        "allergies": "Dust mites, Pollen, Shellfish",
        "doctor": "Dr. P. Rao, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC) & Differentials",
                "tests": [
                    ("Hemoglobin", "14.6", "Normal", "13.0 - 17.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "11,200", "HIGH", "4,000 - 11,000", "/µL"),
                    ("Absolute Eosinophil Count (AEC)", "720.0", "HIGH", "40.0 - 440.0", "cells/µL"),
                    ("Platelet Count", "2.9", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Neutrophils", "48.0", "Normal", "40.0 - 75.0", "%"),
                    ("Lymphocytes", "32.0", "Normal", "20.0 - 40.0", "%"),
                    ("Basophils", "1.2", "HIGH", "0.0 - 1.0", "%"),
                ]
            },
            {
                "name": "Allergy & Specific IgE Panel",
                "tests": [
                    ("Total Serum IgE", "480.0", "HIGH", "< 100.0", "IU/mL"),
                    ("Dust Mite (D. pteronyssinus) sIgE", "12.4", "HIGH", "< 0.35", "kUA/L"),
                    ("Tree & Grass Pollen mix sIgE", "6.8", "HIGH", "< 0.35", "kUA/L"),
                    ("Shellfish (Crab/Shrimp) sIgE", "4.2", "HIGH", "< 0.35", "kUA/L"),
                ]
            },
            {
                "name": "Pulmonary Function & Spirometry",
                "tests": [
                    ("FEV1 (Forced Expiratory Volume 1s)", "2.41 L (68% pred)", "LOW", "> 80% pred", "L"),
                    ("FVC (Forced Vital Capacity)", "3.86 L (87% pred)", "Normal", "> 80% pred", "L"),
                    ("FEV1 / FVC Ratio", "0.62", "LOW", "> 0.75", "ratio"),
                    ("Peak Expiratory Flow Rate (PEFR)", "380 L/min (64% pred)", "LOW", "> 80% pred", "L/min"),
                    ("Post-Bronchodilator FEV1", "2.94 L (83% reversible)", "HIGH", "> 12% reversibility", "L"),
                ]
            },
            {
                "name": "Radiological & Inflammatory Workup",
                "tests": [
                    ("Chest X-Ray (PA View)", "Hyperinflated lung fields, no consolidation, normal cardiac silhouette", "ABNORMAL", "Normal Lung Parenchyma", ""),
                    ("High Sensitivity CRP", "6.8", "HIGH", "< 5.0", "mg/L"),
                ]
            },
            {
                "name": "Hepatic, Renal & Micronutrients",
                "tests": [
                    ("SGPT / ALT", "24.0", "Normal", "7.0 - 56.0", "U/L"),
                    ("Serum Creatinine", "0.90", "Normal", "0.60 - 1.10", "mg/dL"),
                    ("Vitamin D (25-OH)", "32.0", "Normal", "30.0 - 100.0", "ng/mL"),
                    ("Vitamin B12", "420.0", "Normal", "200.0 - 900.0", "pg/mL"),
                ]
            },
        ],
        "impression": "Moderate persistent atopic asthma with significant reversibility; polysensitization to aeroallergens and shellfish."
    },
    {
        "id": "MSK-2026-004",
        "filename": "testreport4.pdf",
        "email": "report4@test.com",
        "name": "Meera Iyer",
        "age": 61,
        "dob": "03-Feb-1964",
        "dob_date": date(1964, 2, 3),
        "gender": "Female",
        "blood_group": "AB+",
        "past_history": "Osteoarthritis (knees), Vitamin D deficiency, Post-menopausal (2013)",
        "allergies": "Sulfa drugs",
        "doctor": "Dr. R. Krishnan, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC) & Inflammation",
                "tests": [
                    ("Hemoglobin", "10.8", "LOW", "12.0 - 15.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "7,100", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.2", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Mean Corpuscular Volume (MCV)", "92.0", "Normal", "80.0 - 100.0", "fL"),
                    ("ESR (Westergren)", "42.0", "HIGH", "0.0 - 20.0", "mm/hr"),
                    ("High Sensitivity CRP (hs-CRP)", "9.2", "HIGH", "< 3.0", "mg/L"),
                ]
            },
            {
                "name": "Bone Mineral & Joint Panel",
                "tests": [
                    ("Vitamin D (25-OH Total)", "12.0", "LOW", "30.0 - 100.0", "ng/mL"),
                    ("Serum Total Calcium", "8.40", "LOW", "8.60 - 10.20", "mg/dL"),
                    ("Ionized Calcium", "4.10", "LOW", "4.50 - 5.30", "mg/dL"),
                    ("Serum Phosphorus", "2.60", "Normal", "2.50 - 4.50", "mg/dL"),
                    ("Alkaline Phosphatase (ALP)", "168.0", "HIGH", "44.0 - 147.0", "U/L"),
                    ("Intact Parathyroid Hormone (PTH)", "78.0", "HIGH", "15.0 - 65.0", "pg/mL"),
                    ("Rheumatoid Factor (RF)", "Negative", "Normal", "Negative (< 14)", "IU/mL"),
                    ("Anti-CCP Antibodies", "Negative", "Normal", "Negative (< 20)", "U/mL"),
                    ("Serum Uric Acid", "6.2", "Normal", "3.4 - 7.0", "mg/dL"),
                ]
            },
            {
                "name": "Renal & Hepatic Function",
                "tests": [
                    ("SGPT / ALT", "28.0", "Normal", "7.0 - 56.0", "U/L"),
                    ("SGOT / AST", "26.0", "Normal", "10.0 - 40.0", "U/L"),
                    ("Serum Creatinine", "1.00", "Normal", "0.60 - 1.10", "mg/dL"),
                    ("Estimated GFR (eGFR)", "68.0", "LOW", "> 90.0", "mL/min"),
                ]
            },
            {
                "name": "Imaging & Bone Densitometry",
                "tests": [
                    ("Digital X-Ray Bilateral Knees", "Grade 3 joint space narrowing, osteophytes, subchondral sclerosis bilaterally", "ABNORMAL", "Normal Joint Space", ""),
                    ("DEXA Scan (Lumbar Spine)", "T-score -2.4 (Osteopenia)", "ABNORMAL", "T-score > -1.0", "SD"),
                    ("DEXA Scan (Femoral Neck)", "T-score -2.8 (Osteoporosis)", "ABNORMAL", "T-score > -1.0", "SD"),
                ]
            },
            {
                "name": "Micronutrients & Vitamins",
                "tests": [
                    ("Vitamin B12", "380.0", "Normal", "200.0 - 900.0", "pg/mL"),
                    ("Serum Folate", "8.10", "Normal", "4.00 - 20.00", "ng/mL"),
                ]
            },
        ],
        "impression": "Primary osteoporosis with Vitamin D deficiency and secondary hyperparathyroidism; bilateral knee OA Grade 3; mild anemia of chronic disease."
    },
    {
        "id": "MSK-2026-005",
        "filename": "testreport5.pdf",
        "email": "report5@test.com",
        "name": "Vikram Singh",
        "age": 45,
        "dob": "18-Sep-1980",
        "dob_date": date(1980, 9, 18),
        "gender": "Male",
        "blood_group": "B-",
        "past_history": "Alcohol use disorder (10+ yrs), Fatty liver (2021), Gout (2020)",
        "allergies": "None",
        "doctor": "Dr. M. Fernandes, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "11.4", "LOW", "13.0 - 17.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "8,600", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "1.1", "LOW", "1.5 - 4.1", "lakh/µL"),
                    ("Mean Corpuscular Volume (MCV)", "104.0", "HIGH", "80.0 - 100.0", "fL"),
                    ("Red Cell Distribution Width (RDW)", "15.8", "HIGH", "11.5 - 14.5", "%"),
                ]
            },
            {
                "name": "Liver Function Tests (LFT) & Coagulation",
                "tests": [
                    ("SGPT / ALT", "112.0", "HIGH", "7.0 - 56.0", "U/L"),
                    ("SGOT / AST", "98.0", "HIGH", "10.0 - 40.0", "U/L"),
                    ("AST / ALT De Ritis Ratio", "0.88", "Normal", "< 1.0", "ratio"),
                    ("Serum Bilirubin Total", "2.10", "HIGH", "0.30 - 1.20", "mg/dL"),
                    ("Serum Bilirubin Direct", "1.30", "HIGH", "0.00 - 0.30", "mg/dL"),
                    ("Serum Albumin", "3.20", "LOW", "3.50 - 5.00", "g/dL"),
                    ("Serum Globulin", "3.60", "HIGH", "2.00 - 3.50", "g/dL"),
                    ("Albumin / Globulin Ratio (A/G)", "0.89", "LOW", "1.00 - 2.00", "ratio"),
                    ("Alkaline Phosphatase (ALP)", "168.0", "HIGH", "44.0 - 147.0", "U/L"),
                    ("Gamma-Glutamyl Transferase (GGT)", "156.0", "HIGH", "9.0 - 48.0", "U/L"),
                    ("Prothrombin Time (PT)", "15.8", "HIGH", "11.0 - 13.5", "seconds"),
                    ("International Normalized Ratio (INR)", "1.40", "HIGH", "0.80 - 1.20", "ratio"),
                ]
            },
            {
                "name": "Renal Function & Electrolytes",
                "tests": [
                    ("Serum Creatinine", "1.10", "Normal", "0.60 - 1.10", "mg/dL"),
                    ("Serum Urea", "32.0", "Normal", "15.0 - 40.0", "mg/dL"),
                    ("Serum Uric Acid", "8.9", "HIGH", "3.4 - 7.0", "mg/dL"),
                    ("Serum Sodium", "132.0", "LOW", "135.0 - 145.0", "mEq/L"),
                    ("Serum Potassium", "3.30", "LOW", "3.50 - 5.00", "mEq/L"),
                ]
            },
            {
                "name": "Lipid Profile & Viral Serology",
                "tests": [
                    ("Total Cholesterol", "246.0", "HIGH", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol", "142.0", "HIGH", "< 100.0", "mg/dL"),
                    ("HDL Cholesterol", "32.0", "LOW", "> 40.0", "mg/dL"),
                    ("Serum Triglycerides", "312.0", "HIGH", "< 150.0", "mg/dL"),
                    ("HBsAg (Hepatitis B Surface Antigen)", "Negative", "Normal", "Negative", ""),
                    ("Anti-HCV (Hepatitis C Antibody)", "Negative", "Normal", "Negative", ""),
                    ("HIV 1 & 2 Rapid Screen", "Negative", "Normal", "Negative", ""),
                ]
            },
            {
                "name": "Abdominal Ultrasonography & FibroScan",
                "tests": [
                    ("USG Whole Abdomen", "Grade 2 hepatic steatosis, coarse echotexture, splenomegaly 13.8 cm, mild ascites", "ABNORMAL", "Normal Liver Architecture", ""),
                    ("Transient Elastography (FibroScan)", "14.2 kPa (F3-F4 Advanced Fibrosis / Cirrhosis)", "ABNORMAL", "< 7.0 kPa", "kPa"),
                ]
            },
            {
                "name": "Routine Urinalysis",
                "tests": [
                    ("Urine Protein", "Trace", "ABNORMAL", "Negative", ""),
                    ("Urine Bilirubin", "1+", "ABNORMAL", "Negative", ""),
                    ("Urobilinogen", "Elevated", "ABNORMAL", "Normal", ""),
                ]
            },
        ],
        "impression": "Alcohol-related cirrhosis (Child-Pugh B) with portal hypertension, thrombocytopenia, macrocytic anemia, hyperuricemia, dyslipidemia."
    },
    {
        "id": "MSK-2026-006",
        "filename": "testreport6.pdf",
        "email": "report6@test.com",
        "name": "Ananya Reddy",
        "age": 39,
        "dob": "27-Dec-1986",
        "dob_date": date(1986, 12, 27),
        "gender": "Female",
        "blood_group": "O-",
        "past_history": "Recurrent UTI, Gestational diabetes (2019), Hypertension (2023)",
        "allergies": "Ciprofloxacin",
        "doctor": "Dr. N. Venkatesh, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "9.6", "LOW", "12.0 - 15.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "10,400", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.1", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("ESR (Westergren)", "48.0", "HIGH", "0.0 - 20.0", "mm/hr"),
                ]
            },
            {
                "name": "Kidney Function Tests (KFT) & Mineral Metabolism",
                "tests": [
                    ("Serum Creatinine", "1.60", "HIGH", "0.60 - 1.10", "mg/dL"),
                    ("Blood Urea Nitrogen (BUN)", "32.0", "HIGH", "7.0 - 20.0", "mg/dL"),
                    ("Estimated GFR (eGFR)", "52.0", "LOW", "> 90.0", "mL/min/1.73m²"),
                    ("Serum Uric Acid", "7.4", "HIGH", "2.4 - 6.0", "mg/dL"),
                    ("Serum Sodium", "136.0", "Normal", "135.0 - 145.0", "mEq/L"),
                    ("Serum Potassium", "5.40", "HIGH", "3.50 - 5.00", "mEq/L"),
                    ("Serum Chloride", "104.0", "Normal", "98.0 - 107.0", "mEq/L"),
                    ("Serum Total Calcium", "8.70", "Normal", "8.60 - 10.20", "mg/dL"),
                    ("Serum Phosphorus", "4.60", "HIGH", "2.50 - 4.50", "mg/dL"),
                    ("Intact PTH (iPTH)", "92.0", "HIGH", "15.0 - 65.0", "pg/mL"),
                ]
            },
            {
                "name": "Urinalysis & Urine Culture",
                "tests": [
                    ("Urine Protein", "2+", "ABNORMAL", "Negative", ""),
                    ("Urine Occult Blood", "1+", "ABNORMAL", "Negative", ""),
                    ("Urine Pus Cells", "18-20", "HIGH", "0 - 5", "/hpf"),
                    ("Urine Red Blood Cells (RBC)", "6-8", "HIGH", "0 - 2", "/hpf"),
                    ("Urine Culture & Sensitivity", "E. coli > 10^5 CFU/mL isolated", "ABNORMAL", "Sterile (< 10^3)", "CFU/mL"),
                    ("24-Hour Urinary Total Protein", "1.60", "HIGH", "< 0.15", "g/day"),
                ]
            },
            {
                "name": "Glycemic & Lipid Assessment",
                "tests": [
                    ("Fasting Blood Glucose", "118.0", "HIGH", "70.0 - 100.0", "mg/dL"),
                    ("HbA1c (Glycated Hemoglobin)", "6.9", "HIGH", "< 5.7", "%"),
                    ("Total Cholesterol", "208.0", "HIGH", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol", "128.0", "HIGH", "< 100.0", "mg/dL"),
                    ("HDL Cholesterol", "42.0", "Normal", "> 40.0", "mg/dL"),
                    ("Serum Triglycerides", "168.0", "HIGH", "< 150.0", "mg/dL"),
                ]
            },
            {
                "name": "Renal Imaging & Cardiac Assessment",
                "tests": [
                    ("USG KUB (Kidney, Ureter, Bladder)", "Bilateral small kidneys (R: 8.4 cm, L: 8.1 cm), increased cortical echogenicity", "ABNORMAL", "R: 10-12 cm, L: 10-12 cm", ""),
                    ("Renal Artery Doppler", "Normal bilateral renal artery resistive index and laminar flow", "Normal", "Laminar Flow", ""),
                    ("12-Lead Electrocardiogram (ECG)", "Left Ventricular Hypertrophy (LVH), no acute ischemic changes", "ABNORMAL", "Normal Tracing", ""),
                ]
            },
        ],
        "impression": "CKD Stage 3a (hypertensive + diabetic nephropathy), secondary hyperparathyroidism, active E. coli UTI, proteinuria, hyperkalemia."
    },
    {
        "id": "MSK-2026-007",
        "filename": "testreport7.pdf",
        "email": "report7@test.com",
        "name": "Karan Malhotra",
        "age": 24,
        "dob": "05-May-2001",
        "dob_date": date(2001, 5, 5),
        "gender": "Male",
        "blood_group": "A-",
        "past_history": "None",
        "allergies": "Peanuts (anaphylaxis history)",
        "doctor": "Dr. T. Deshpande, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC) & RBC Indices",
                "tests": [
                    ("Hemoglobin", "8.9", "LOW", "13.0 - 17.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "5,800", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "3.9", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Mean Corpuscular Volume (MCV)", "68.0", "LOW", "80.0 - 100.0", "fL"),
                    ("Mean Corpuscular Hemoglobin (MCH)", "22.0", "LOW", "27.0 - 33.0", "pg"),
                    ("MCHC", "29.0", "LOW", "32.0 - 36.0", "g/dL"),
                    ("Red Cell Distribution Width (RDW)", "17.2", "HIGH", "11.5 - 14.5", "%"),
                    ("Reticulocyte Count", "0.8", "Normal", "0.5 - 2.5", "%"),
                ]
            },
            {
                "name": "Iron Metabolism & Ferritin Dynamics",
                "tests": [
                    ("Serum Ferritin", "6.0", "LOW", "30.0 - 400.0", "ng/mL"),
                    ("Serum Iron", "32.0", "LOW", "60.0 - 170.0", "µg/dL"),
                    ("Total Iron Binding Capacity (TIBC)", "480.0", "HIGH", "250.0 - 450.0", "µg/dL"),
                    ("Transferrin Saturation", "7.0", "LOW", "20.0 - 50.0", "%"),
                    ("Soluble Transferrin Receptor (sTfR)", "Elevated", "HIGH", "Normal Range", ""),
                ]
            },
            {
                "name": "Peripheral Blood Smear Examination",
                "tests": [
                    ("RBC Morphology", "Marked microcytic hypochromic RBCs, moderate anisopoikilocytosis, target cells seen", "ABNORMAL", "Normocytic Normochromic", ""),
                    ("WBC Morphology", "Normal maturity and distribution. No immature blasts or dysplastic changes", "Normal", "Normal", ""),
                    ("Platelet Morphology", "Adequate in smear, morphologically normal", "Normal", "Normal", ""),
                ]
            },
            {
                "name": "Micronutrients & Organ Safety",
                "tests": [
                    ("Vitamin B12", "340.0", "Normal", "200.0 - 900.0", "pg/mL"),
                    ("Serum Folate", "6.80", "Normal", "4.00 - 20.00", "ng/mL"),
                    ("Vitamin D (25-OH)", "28.0", "LOW", "30.0 - 100.0", "ng/mL"),
                    ("SGPT / ALT", "22.0", "Normal", "7.0 - 56.0", "U/L"),
                    ("Serum Creatinine", "0.90", "Normal", "0.60 - 1.10", "mg/dL"),
                ]
            },
            {
                "name": "Stool Examination & Occult Blood",
                "tests": [
                    ("Stool Ova & Parasites", "Negative", "Normal", "Negative", ""),
                    ("Stool Occult Blood (FOBT)", "Positive (in 3 consecutive samples)", "ABNORMAL", "Negative", ""),
                ]
            },
        ],
        "impression": "Severe iron deficiency anemia; occult GI bleed workup advised (UGI endoscopy + colonoscopy)."
    },
    {
        "id": "MSK-2026-008",
        "filename": "testreport8.pdf",
        "email": "report8@test.com",
        "name": "Sneha Nair",
        "age": 30,
        "dob": "11-Aug-1995",
        "dob_date": date(1995, 8, 11),
        "gender": "Female",
        "blood_group": "B+",
        "past_history": "PCOS (2022), Irregular cycles",
        "allergies": "Latex",
        "doctor": "Dr. L. Menon, MD",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "12.4", "Normal", "12.0 - 15.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "6,900", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.8", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Mean Corpuscular Volume (MCV)", "94.0", "Normal", "80.0 - 100.0", "fL"),
                ]
            },
            {
                "name": "Endocrine & Hormonal Profile (Day 3)",
                "tests": [
                    ("Luteinizing Hormone (LH)", "12.4", "HIGH", "2.0 - 12.0", "mIU/mL"),
                    ("Follicle Stimulating Hormone (FSH)", "4.4", "Normal", "3.0 - 12.0", "mIU/mL"),
                    ("LH / FSH Ratio", "2.8", "HIGH", "< 2.0", "ratio"),
                    ("Total Testosterone", "68.0", "HIGH", "15.0 - 70.0", "ng/dL"),
                    ("DHEA-Sulfate (DHEA-S)", "320.0", "Normal", "35.0 - 430.0", "µg/dL"),
                    ("Serum Prolactin", "24.0", "HIGH", "4.0 - 23.0", "ng/mL"),
                    ("Anti-Müllerian Hormone (AMH)", "7.8", "HIGH", "1.0 - 4.0", "ng/mL"),
                    ("17-OH Progesterone", "1.40", "Normal", "< 2.00", "ng/mL"),
                ]
            },
            {
                "name": "Thyroid & Metabolic Insulin Resistance",
                "tests": [
                    ("TSH (Thyroid Stimulating Hormone)", "3.20", "Normal", "0.40 - 4.00", "µIU/mL"),
                    ("Free Thyroxine (FT4)", "1.20", "Normal", "0.80 - 1.80", "ng/dL"),
                    ("Fasting Blood Glucose", "96.0", "Normal", "70.0 - 100.0", "mg/dL"),
                    ("Fasting Serum Insulin", "18.0", "HIGH", "2.0 - 19.0", "µIU/mL"),
                    ("HOMA-IR (Insulin Resistance Index)", "4.3", "HIGH", "< 2.5", "index"),
                    ("HbA1c", "5.6", "Normal", "< 5.7", "%"),
                ]
            },
            {
                "name": "Lipid Profile & Micronutrients",
                "tests": [
                    ("Total Cholesterol", "196.0", "Normal", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol", "122.0", "HIGH", "< 100.0", "mg/dL"),
                    ("HDL Cholesterol", "38.0", "LOW", "> 40.0", "mg/dL"),
                    ("Serum Triglycerides", "178.0", "HIGH", "< 150.0", "mg/dL"),
                    ("Vitamin B12", "148.0", "LOW", "200.0 - 900.0", "pg/mL"),
                    ("Serum Folate", "3.10", "LOW", "4.00 - 20.00", "ng/mL"),
                    ("Vitamin D (25-OH)", "21.0", "LOW", "30.0 - 100.0", "ng/mL"),
                ]
            },
            {
                "name": "Pelvic Ultrasound (TVS)",
                "tests": [
                    ("Pelvic Sonography", "Bilateral ovaries enlarged with >= 12 small peripheral follicles (2-9 mm), stromal hypertrophy; Endometrial thickness 6 mm", "ABNORMAL", "Normal Follicular Pattern", ""),
                ]
            },
        ],
        "impression": "PCOS (Rotterdam criteria) with insulin resistance, Vitamin B12 and folate deficiency, Vitamin D insufficiency, dyslipidemia."
    },
    {
        "id": "MSK-2026-009",
        "filename": "testreport9.pdf",
        "email": "report9@test.com",
        "name": "Rohit Verma",
        "age": 58,
        "dob": "30-Jan-1967",
        "dob_date": date(1967, 1, 30),
        "gender": "Male",
        "blood_group": "AB-",
        "past_history": "CABG (2022, triple vessel), Hypertension, Dyslipidemia, Aspirin GI intolerance",
        "allergies": "Aspirin (GI bleed)",
        "doctor": "Dr. K. Subramaniam, DM",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "13.8", "Normal", "13.0 - 17.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "7,400", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.3", "Normal", "1.5 - 4.1", "lakh/µL"),
                ]
            },
            {
                "name": "Cardiac Biomarkers & Risk Stratification",
                "tests": [
                    ("Troponin I (High Sensitivity)", "0.02", "Normal", "< 0.04", "ng/mL"),
                    ("CK-MB (Mass)", "14.0", "Normal", "< 25.0", "U/L"),
                    ("NT-proBNP", "320.0", "HIGH", "< 125.0", "pg/mL"),
                    ("Serum Homocysteine", "18.0", "HIGH", "5.0 - 15.0", "µmol/L"),
                    ("High Sensitivity CRP (hs-CRP)", "4.8", "HIGH", "< 1.0", "mg/L"),
                ]
            },
            {
                "name": "Lipid & Atherosclerosis Panel",
                "tests": [
                    ("Total Cholesterol", "168.0", "Normal", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol", "92.0", "HIGH", "< 70.0 (post-CABG target)", "mg/dL"),
                    ("HDL Cholesterol", "40.0", "Normal", "> 40.0", "mg/dL"),
                    ("Serum Triglycerides", "148.0", "Normal", "< 150.0", "mg/dL"),
                    ("Lipoprotein (a) [Lp(a)]", "62.0", "HIGH", "< 30.0", "mg/dL"),
                ]
            },
            {
                "name": "Coagulation & Anticoagulation Monitoring",
                "tests": [
                    ("Prothrombin Time (PT)", "15.2", "HIGH", "11.0 - 13.5", "seconds"),
                    ("International Normalized Ratio (INR)", "2.40", "Normal", "2.00 - 3.00 (Warfarin Target)", "ratio"),
                    ("Activated Partial Thromboplastin Time (aPTT)", "34.0", "Normal", "25.0 - 35.0", "seconds"),
                ]
            },
            {
                "name": "Hepato-Renal & Glycemic Status",
                "tests": [
                    ("SGPT / ALT", "34.0", "Normal", "7.0 - 56.0", "U/L"),
                    ("SGOT / AST", "30.0", "Normal", "10.0 - 40.0", "U/L"),
                    ("Serum Creatinine", "1.10", "Normal", "0.60 - 1.10", "mg/dL"),
                    ("Estimated GFR (eGFR)", "72.0", "LOW", "> 90.0", "mL/min"),
                    ("Serum Potassium", "4.40", "Normal", "3.50 - 5.00", "mEq/L"),
                    ("Fasting Blood Glucose", "108.0", "HIGH", "70.0 - 100.0", "mg/dL"),
                    ("HbA1c", "6.4", "HIGH", "< 5.7", "%"),
                ]
            },
            {
                "name": "Cardiovascular Imaging & Investigations",
                "tests": [
                    ("12-Lead Electrocardiogram (ECG)", "Normal sinus rhythm, old anterior wall myocardial infarction (Q-waves in V1-V3)", "ABNORMAL", "Normal Sinus Rhythm", ""),
                    ("2D Transthoracic Echocardiogram", "LVEF 48%, anterior wall regional hypokinesia, mild mitral regurgitation (MR)", "ABNORMAL", "LVEF >= 55%", "%"),
                    ("Carotid Doppler Ultrasound", "30% atherosclerotic plaque stenosis in right internal carotid artery (ICA)", "ABNORMAL", "No Significant Stenosis", ""),
                ]
            },
        ],
        "impression": "Post-CABG (2022) with reduced LVEF (48%), suboptimal LDL control despite statin, elevated Lp(a) and homocysteine, on warfarin with therapeutic INR."
    },
    {
        "id": "MSK-2026-010",
        "filename": "testreport10.pdf",
        "email": "report10@test.com",
        "name": "Ishita Bose",
        "age": 22,
        "dob": "19-Apr-2003",
        "dob_date": date(2003, 4, 19),
        "gender": "Female",
        "blood_group": "O+",
        "past_history": "None",
        "allergies": "None",
        "doctor": "Dr. V. Chatterjee, MBBS",
        "date": "29-Sep-2026",
        "panels": [
            {
                "name": "Complete Blood Count (CBC)",
                "tests": [
                    ("Hemoglobin", "13.4", "Normal", "12.0 - 15.0", "g/dL"),
                    ("WBC (Total Leucocyte Count)", "7,200", "Normal", "4,000 - 11,000", "/µL"),
                    ("Platelet Count", "2.6", "Normal", "1.5 - 4.1", "lakh/µL"),
                    ("Mean Corpuscular Volume (MCV)", "88.0", "Normal", "80.0 - 100.0", "fL"),
                    ("Mean Corpuscular Hemoglobin (MCH)", "30.0", "Normal", "27.0 - 33.0", "pg"),
                    ("ESR (Westergren)", "8.0", "Normal", "0.0 - 20.0", "mm/hr"),
                ]
            },
            {
                "name": "Metabolic & Glycemic Profile",
                "tests": [
                    ("Fasting Blood Glucose", "88.0", "Normal", "70.0 - 100.0", "mg/dL"),
                    ("HbA1c (Glycated Hemoglobin)", "5.2", "Normal", "< 5.7", "%"),
                    ("Fasting Serum Insulin", "8.0", "Normal", "2.0 - 19.0", "µIU/mL"),
                ]
            },
            {
                "name": "Lipid Profile",
                "tests": [
                    ("Total Cholesterol", "172.0", "Normal", "< 200.0", "mg/dL"),
                    ("LDL Cholesterol", "92.0", "Normal", "< 100.0", "mg/dL"),
                    ("HDL Cholesterol", "58.0", "Normal", "> 40.0", "mg/dL"),
                    ("Serum Triglycerides", "96.0", "Normal", "< 150.0", "mg/dL"),
                ]
            },
            {
                "name": "Thyroid Function Tests",
                "tests": [
                    ("TSH (Ultrasensitive)", "2.10", "Normal", "0.40 - 4.00", "µIU/mL"),
                    ("Free Thyroxine (FT4)", "1.10", "Normal", "0.80 - 1.80", "ng/dL"),
                ]
            },
            {
                "name": "Liver & Kidney Function",
                "tests": [
                    ("SGPT / ALT", "18.0", "Normal", "7.0 - 56.0", "U/L"),
                    ("SGOT / AST", "20.0", "Normal", "10.0 - 40.0", "U/L"),
                    ("Serum Bilirubin Total", "0.70", "Normal", "0.30 - 1.20", "mg/dL"),
                    ("Serum Creatinine", "0.70", "Normal", "0.60 - 1.10", "mg/dL"),
                    ("Serum Urea", "22.0", "Normal", "15.0 - 40.0", "mg/dL"),
                ]
            },
            {
                "name": "Vitamins & Micronutrients",
                "tests": [
                    ("Vitamin D (25-OH)", "38.0", "Normal", "30.0 - 100.0", "ng/mL"),
                    ("Vitamin B12", "520.0", "Normal", "200.0 - 900.0", "pg/mL"),
                    ("Serum Folate", "12.0", "Normal", "4.00 - 20.00", "ng/mL"),
                ]
            },
            {
                "name": "Routine Urinalysis",
                "tests": [
                    ("Urine Protein", "Negative", "Normal", "Negative", ""),
                    ("Urine Glucose", "Negative", "Normal", "Negative", ""),
                    ("Pus Cells", "0-1", "Normal", "0 - 5", "/hpf"),
                    ("RBCs", "Nil", "Normal", "0 - 2", "/hpf"),
                ]
            },
            {
                "name": "Vitals & Physiological Assessment",
                "tests": [
                    ("Blood Pressure", "112/72", "Normal", "90-120 / 60-80", "mmHg"),
                    ("Heart Rate (Resting)", "68", "Normal", "60 - 100", "bpm"),
                    ("Body Mass Index (BMI)", "21.8", "Normal", "18.5 - 24.9", "kg/m²"),
                    ("12-Lead Resting ECG", "Normal sinus rhythm", "Normal", "Normal Sinus Rhythm", ""),
                ]
            },
        ],
        "impression": "All parameters within normal limits. Healthy individual. No abnormalities detected."
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# PDF Generator using ReportLab
# ─────────────────────────────────────────────────────────────────────────────
def build_pdf_report(report_data: dict, output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0F172A"),
    )
    brand_sub_style = ParagraphStyle(
        "BrandSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )
    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=4,
    )
    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )
    meta_val = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )
    th_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    tb_test = ParagraphStyle(
        "TableTest",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A"),
    )
    tb_normal = ParagraphStyle(
        "TableNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1E293B"),
    )
    tb_abnormal = ParagraphStyle(
        "TableAbnormal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#DC2626"),
    )
    tb_flag_normal = ParagraphStyle(
        "TableFlagNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#64748B"),
    )
    tb_flag_abnormal = ParagraphStyle(
        "TableFlagAbnormal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#DC2626"),
    )
    impression_text_style = ParagraphStyle(
        "ImpressionText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # ── 1. Lab Header & Accreditation ──
    header_table_data = [
        [
            Paragraph("<b>MEDISKYE CLINICAL LABORATORIES & DIAGNOSTIC CENTER</b>", brand_title_style),
            Paragraph("<font size=8 color='#0284C7'><b>ACCESSION REPORT</b></font><br/><font size=7 color='#64748B'>CONFIDENTIAL MEDICAL RECORD</font>", ParagraphStyle("RightH", parent=styles["Normal"], alignment=2)),
        ],
        [
            Paragraph("NABL Accredited Reference Laboratory • ISO 15189:2022 Certified • CAP Inspection #89201<br/>Central Facility: 42 Health Boulevard, Tech City, Bengaluru 560100 • Helpline: 1800-419-MEDISKYE", brand_sub_style),
            Paragraph(f"<b>Report ID:</b> {report_data['id']}<br/><b>Date:</b> {report_data['date']}", ParagraphStyle("RightH2", parent=styles["Normal"], alignment=2, fontName="Helvetica", fontSize=7.5, leading=10, textColor=colors.HexColor("#334155"))),
        ],
    ]
    header_table = Table(header_table_data, colWidths=[380, 143])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F172A"), spaceBefore=2, spaceAfter=6))

    # ── 2. Patient Demographics & Doctor Info Block ──
    patient_info_data = [
        [
            Paragraph("<b>Patient Name:</b>", meta_label),
            Paragraph(f"<b>{report_data['name']}</b>", meta_val),
            Paragraph("<b>Report ID:</b>", meta_label),
            Paragraph(f"<b>{report_data['id']}</b>", meta_val),
        ],
        [
            Paragraph("<b>Age / Gender:</b>", meta_label),
            Paragraph(f"{report_data['age']} Yrs / {report_data['gender']}", meta_val),
            Paragraph("<b>Report Date:</b>", meta_label),
            Paragraph(report_data['date'], meta_val),
        ],
        [
            Paragraph("<b>Date of Birth:</b>", meta_label),
            Paragraph(report_data['dob'], meta_val),
            Paragraph("<b>Referring Doctor:</b>", meta_label),
            Paragraph(f"<b>{report_data['doctor']}</b>", meta_val),
        ],
        [
            Paragraph("<b>Blood Group:</b>", meta_label),
            Paragraph(f"<b>{report_data['blood_group']}</b>", meta_val),
            Paragraph("<b>Specimen:</b>", meta_label),
            Paragraph("Blood (Serum / Plasma / EDTA)", meta_val),
        ],
    ]
    pinfo_table = Table(patient_info_data, colWidths=[80, 180, 90, 173])
    pinfo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(pinfo_table)
    story.append(Spacer(1, 5))

    # ── 3. Past Medical History & Allergies Section ──
    has_allergy = report_data["allergies"].strip().lower() not in ["none", "nil", ""]
    allergy_bg = colors.HexColor("#FEF2F2") if has_allergy else colors.HexColor("#F8FAFC")
    allergy_border = colors.HexColor("#EF4444") if has_allergy else colors.HexColor("#CBD5E1")
    allergy_html = (
        f"<font color='#DC2626'><b>CRITICAL ALLERGY ALERT:</b> {report_data['allergies']}</font>"
        if has_allergy
        else "<b>Allergies:</b> None Reported"
    )

    clinical_data = [
        [
            Paragraph(f"<b>Past Medical History:</b> {report_data['past_history']}", meta_val),
            Paragraph(allergy_html, meta_val),
        ]
    ]
    clinical_table = Table(clinical_data, colWidths=[310, 213])
    clinical_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (1, 0), (1, 0), allergy_bg),
        ('BOX', (0, 0), (0, 0), 0.6, colors.HexColor("#CBD5E1")),
        ('BOX', (1, 0), (1, 0), 0.8, allergy_border),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(clinical_table)
    story.append(Spacer(1, 6))

    # ── 4. Test Panels with Proper Tables ──
    col_widths = [185, 80, 52, 136, 70]  # Sum = 523 pt (fits A4 with 36pt margins)

    for panel in report_data["panels"]:
        panel_elements = []

        # Panel Header Banner
        panel_title_p = Paragraph(f"<b>PANEL: {panel['name'].upper()}</b>", ParagraphStyle(
            "PanelH",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#0F172A"),
        ))
        panel_elements.append(panel_title_p)
        panel_elements.append(Spacer(1, 2))

        # Table Header
        table_rows = [
            [
                Paragraph("<b>TEST DESCRIPTION</b>", th_style),
                Paragraph("<b>OBSERVED</b>", th_style),
                Paragraph("<b>FLAG</b>", th_style),
                Paragraph("<b>REFERENCE RANGE</b>", th_style),
                Paragraph("<b>UNITS</b>", th_style),
            ]
        ]

        row_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('TOPPADDING', (0, 0), (-1, 0), 3),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
            ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]

        for idx, (test_name, result, flag, ref_range, units) in enumerate(panel["tests"]):
            row_idx = idx + 1
            is_abnormal = flag.upper() in ["HIGH", "LOW", "ABNORMAL"]
            val_style = tb_abnormal if is_abnormal else tb_normal
            flag_style = tb_flag_abnormal if is_abnormal else tb_flag_normal

            row_bg = colors.HexColor("#FEF2F2") if is_abnormal else (colors.HexColor("#F8FAFC") if idx % 2 == 1 else colors.white)
            row_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), row_bg))

            row_data = [
                Paragraph(test_name, tb_test),
                Paragraph(f"<b>{result}</b>" if is_abnormal else result, val_style),
                Paragraph(flag.upper(), flag_style),
                Paragraph(ref_range, tb_normal),
                Paragraph(units, tb_normal),
            ]
            table_rows.append(row_data)

        panel_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
        panel_table.setStyle(TableStyle(row_styles))
        panel_elements.append(panel_table)
        panel_elements.append(Spacer(1, 5))

        # Keep short panels together
        if len(panel["tests"]) <= 5:
            story.append(KeepTogether(panel_elements))
        else:
            story.extend(panel_elements)

    # ── 5. Doctor's Impression / Remarks Section ──
    story.append(Spacer(1, 4))
    impression_data = [
        [
            Paragraph("<b>DOCTOR'S IMPRESSION / REMARKS:</b>", ParagraphStyle(
                "ImpTitle",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#0369A1"),
            ))
        ],
        [
            Paragraph(report_data["impression"], impression_text_style)
        ]
    ]
    impression_table = Table(impression_data, colWidths=[523])
    impression_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#0284C7")),
        ('LINEBEFORE', (0, 0), (0, -1), 3.5, colors.HexColor("#0284C7")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # ── 6. Pathologist & Quality Signatures ──
    sign_data = [
        [
            Paragraph("<b>Reported by:</b><br/>Dr. Meenakshi Sunder, MD<br/><font size=7 color='#64748B'>Consultant Biochemist</font>", meta_val),
            Paragraph("<b>Verified by:</b><br/>Dr. Rajeshwar Sen, MD (Path)<br/><font size=7 color='#64748B'>Senior Consultant Pathologist</font>", meta_val),
            Paragraph("<b>Accreditation Director:</b><br/>Dr. K. R. Sharma, PhD<br/><font size=7 color='#64748B'>Quality Assurance Head</font>", meta_val),
        ]
    ]
    sign_table = Table(sign_data, colWidths=[174, 174, 175])
    sign_table.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ]))

    end_block = KeepTogether([
        impression_table,
        Spacer(1, 6),
        sign_table,
    ])
    story.append(end_block)

    # Build PDF with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Generate All 10 PDFs
# ─────────────────────────────────────────────────────────────────────────────
def generate_all_pdfs():
    print("\n" + "=" * 60)
    print("TASK 1: Generating 10 Medical Lab Report PDFs")
    print("=" * 60)

    # Output directories: Both workspace root and app root
    workspace_root = backend_dir.parent.parent
    app_root = backend_dir.parent

    target_dirs = [
        workspace_root / "test_reports",
        app_root / "test_reports",
    ]

    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)

    generated_files = []
    for rdata in REPORTS_DATA:
        fname = rdata["filename"]
        # Generate to app_root / test_reports
        primary_path = app_root / "test_reports" / fname
        build_pdf_report(rdata, str(primary_path))

        # Copy or generate to workspace_root / test_reports
        secondary_path = workspace_root / "test_reports" / fname
        if secondary_path != primary_path:
            with open(primary_path, "rb") as src, open(secondary_path, "wb") as dst:
                dst.write(src.read())

        size_kb = primary_path.stat().st_size / 1024
        print(f"  ✓ Generated: {fname:<18} ({size_kb:5.1f} KB) - {rdata['name']} ({rdata['gender']}, {rdata['age']}y)")
        generated_files.append(primary_path)

    print(f"\nSuccessfully generated {len(generated_files)} PDFs in:")
    for d in target_dirs:
        print(f"  → {d.resolve()}")
    return target_dirs[0]


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Seed Users, Associate Documents, and Validate End-to-End
# ─────────────────────────────────────────────────────────────────────────────
async def seed_and_validate():
    print("\n" + "=" * 60)
    print("TASK 2: Seeding User Profiles, Pre-linking Documents & Validating RAG")
    print("=" * 60)

    from sqlalchemy.future import select
    from app.db.database import AsyncSessionLocal
    from app.db.models import User, Document, Chat
    from app.core.auth import get_password_hash
    from app.core.config import settings
    from app.rag.loader import extract_text_from_file
    from app.rag.retriever import create_hybrid_index, load_hybrid_index

    # Base PDF directory
    pdf_dir = backend_dir.parent / "test_reports"
    index_dir = settings.BASE_DIR / "indexes"
    index_dir.mkdir(exist_ok=True)

    hashed_pw = get_password_hash("123456")

    async with AsyncSessionLocal() as session:
        for rdata in REPORTS_DATA:
            email = rdata["email"]
            print(f"\nProcessing User: {rdata['name']} <{email}>")

            # 1. Upsert User
            res = await session.execute(select(User).filter(User.email == email))
            user = res.scalars().first()
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    hashed_password=hashed_pw,
                    full_name=rdata["name"],
                    date_of_birth=rdata["dob_date"],
                    biological_sex=rdata["gender"],
                    blood_type=rdata["blood_group"],
                    pre_existing_conditions=rdata["past_history"],
                    known_allergies=rdata["allergies"],
                    phi_consent_granted=True,
                    consent_timestamp=datetime.now(timezone.utc),
                    language_preference="English",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                print(f"  ✓ Created user account (ID: {user.id})")
            else:
                user.hashed_password = hashed_pw
                user.full_name = rdata["name"]
                user.date_of_birth = rdata["dob_date"]
                user.biological_sex = rdata["gender"]
                user.blood_type = rdata["blood_group"]
                user.pre_existing_conditions = rdata["past_history"]
                user.known_allergies = rdata["allergies"]
                user.phi_consent_granted = True
                await session.commit()
                print(f"  ✓ Updated existing user account (ID: {user.id})")

            # 2. Check / Create Document Record
            pdf_path = pdf_dir / rdata["filename"]
            if not pdf_path.exists():
                print(f"  ✗ ERROR: PDF not found at {pdf_path}")
                continue

            doc_res = await session.execute(
                select(Document).filter(
                    Document.user_id == user.id,
                    Document.filename == rdata["filename"]
                )
            )
            doc = doc_res.scalars().first()
            if not doc:
                doc = Document(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    filename=rdata["filename"],
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)
                print(f"  ✓ Created document record (ID: {doc.id})")

            # 3. End-to-End Extraction & Hybrid Indexing
            index_path = str(index_dir / f"user_{user.id}_doc_{doc.id}.index")
            print(f"  → Running RAG Analyzer on {rdata['filename']}...")
            
            page_docs = await extract_text_from_file(str(pdf_path), rdata["filename"])
            total_chars = sum(len(d.page_content.strip()) for d in page_docs)
            print(f"    ✓ Extracted {len(page_docs)} pages, {total_chars} total characters.")

            if total_chars < 100:
                raise RuntimeError(f"Extraction failed: only {total_chars} chars extracted from {pdf_path}")

            # Verify key text is extracted
            extracted_text = " ".join(d.page_content for d in page_docs)
            assert rdata["name"].lower() in extracted_text.lower(), f"Patient name not found in extracted text!"
            print(f"    ✓ Patient name '{rdata['name']}' confirmed in extracted text.")

            # Create Hybrid FAISS + BM25 Index
            vectorstore, bm25_index, chunks = create_hybrid_index(page_docs, index_path)
            print(f"    ✓ Hybrid index created with {len(chunks)} chunks at {Path(index_path).name}")

            # Update document file_path
            doc.file_path = index_path
            await session.commit()

            # 4. Create Initial Welcoming Chat Message if none exists
            chat_res = await session.execute(
                select(Chat).filter(Chat.document_id == doc.id)
            )
            existing_chats = chat_res.scalars().all()
            if not existing_chats:
                welcome_msg = (
                    f"Hello {rdata['name']}, your laboratory report ({rdata['filename']}) has been analyzed and indexed. "
                    f"Our clinical findings note: {rdata['impression']}\n\n"
                    "Feel free to ask any questions about your lab values, reference ranges, or recommendations."
                )
                ai_chat = Chat(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    document_id=doc.id,
                    role="ai",
                    message=welcome_msg,
                )
                session.add(ai_chat)
                await session.commit()
                print(f"    ✓ Pre-initialized consultation chat record.")

            # 5. Validate Retrieval End-to-End
            loaded_vs, loaded_bm25 = load_hybrid_index(index_path)
            query_test = "abnormal test results or doctor impression"
            retrieved_docs = loaded_vs.similarity_search(query_test, k=2)
            assert len(retrieved_docs) > 0, "Retrieval returned 0 documents!"
            print(f"    ✓ FAISS retrieval test passed ({len(retrieved_docs)} relevant chunks matched).")

    print("\n" + "=" * 60)
    print("ALL 10 USER PROFILES & TEST REPORTS SUCCESSFULLY SEEDED & VALIDATED")
    print("=" * 60)


if __name__ == "__main__":
    generate_all_pdfs()
    asyncio.run(seed_and_validate())
