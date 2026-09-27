from fastapi import APIRouter, Depends, Query

from auth import require_staff
from agents.university_agent import university_agent


router = APIRouter(
    prefix="/api/programs",
    tags=["Verified Program Catalog"],
    dependencies=[Depends(require_staff)],
)


@router.get("")
def list_programs(
    search: str | None = None,
    country: str | None = None,
):
    programs = university_agent.get_all_programs()
    if search:
        needle = search.strip().casefold()
        programs = [
            item
            for item in programs
            if needle
            in " ".join(
                str(item[field])
                for field in (
                    "university",
                    "program",
                    "country",
                    "fee_per_year",
                    "documents_needed",
                )
            ).casefold()
        ]
    if country:
        country_key = country.strip().casefold()
        programs = [
            item for item in programs
            if item["country"].casefold() == country_key
        ]
    return {"programs": programs, "total": len(programs)}
