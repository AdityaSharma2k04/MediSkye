from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.db.models import Specialist

async def get_recommended_specialists(db: AsyncSession, flags: List[str]) -> List[dict]:
    """
    Query the Specialist table for doctors whose keywords intersect with the given flags.
    Returns a list of dictionaries with specialist details.
    """
    if not flags:
        return []

    # Get all specialists (in a huge DB we'd use json operators, but here we can filter in python or basic SQL)
    result = await db.execute(select(Specialist))
    specialists = result.scalars().all()
    
    recommended = []
    # Normalize flags for case-insensitive matching
    flags_lower = {f.lower() for f in flags}

    for sp in specialists:
        # Check for intersection
        sp_keywords = {k.lower() for k in sp.keywords} if sp.keywords else set()
        if flags_lower.intersection(sp_keywords):
            recommended.append({
                "id": str(sp.id),
                "name": sp.name,
                "specialty": sp.specialty,
                "contact_info": sp.contact_info,
                "matched_flags": list(flags_lower.intersection(sp_keywords))
            })
            
    # Remove duplicates if any (though DB shouldn't have exact same objects) and sort by number of matched flags
    recommended.sort(key=lambda x: len(x["matched_flags"]), reverse=True)
    
    return recommended
