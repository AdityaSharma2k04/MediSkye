from datetime import date
from typing import Optional

def calculate_age(dob: Optional[date]) -> Optional[int]:
    """
    Calculate exact age dynamically based on the current system date.
    
    Args:
        dob: The date of birth.
        
    Returns:
        int: The exact age in years, or None if dob is not provided.
    """
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
