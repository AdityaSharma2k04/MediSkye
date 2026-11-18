from typing import Any


def compute_bmi_info(height_cm: float | None, weight_kg: float | None) -> dict[str, Any] | None:
    """
    Calculates Body Mass Index (BMI) and standard WHO clinical categorization.
    Expects height in centimeters and weight in kilograms.

    BMI Categories:
      - Underweight: < 18.5
      - Normal weight: 18.5 - 24.9
      - Overweight: 25.0 - 29.9
      - Obese: >= 30.0
    """
    if height_cm is None or weight_kg is None:
        return None
    try:
        h = float(height_cm)
        w = float(weight_kg)
        if h <= 0 or w <= 0 or h > 300 or w > 600:
            return None
        height_m = h / 100.0
        bmi = round(w / (height_m * height_m), 1)
        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25.0:
            category = "Normal weight"
        elif bmi < 30.0:
            category = "Overweight"
        else:
            category = "Obese"
        return {
            "bmi": bmi,
            "category": category,
            "formatted": f"{bmi} kg/m² ({category})",
        }
    except (ValueError, TypeError, ZeroDivisionError):
        return None
