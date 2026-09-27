from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import (
    create_staff_user,
    get_current_staff,
    list_staff_users,
    require_admin,
    update_staff_user,
)


router = APIRouter(
    prefix="/api/staff",
    tags=["Staff Management"],
    dependencies=[Depends(require_admin)],
)


class StaffCreateInput(BaseModel):
    name: str
    email: str
    password: str
    role: Literal["admin", "counselor"] = "counselor"


class StaffUpdateInput(BaseModel):
    name: str | None = None
    role: Literal["admin", "counselor"] | None = None
    is_active: bool | None = None
    password: str | None = None


def raise_staff_error(result: dict):
    error = result.get("error")
    if error is None:
        return
    if error == "staff_not_found":
        raise HTTPException(status_code=404, detail="Staff user not found.")
    if error in {"email_already_exists", "last_active_admin"}:
        raise HTTPException(status_code=409, detail=error)
    if error in {
        "name_required",
        "invalid_email",
        "invalid_role",
        "invalid_password",
        "invalid_active_state",
        "no_valid_changes",
    }:
        raise HTTPException(status_code=422, detail=error)
    raise HTTPException(status_code=400, detail="Staff operation could not be completed.")


@router.get("")
def get_staff():
    return {"staff": list_staff_users()}


@router.post("", status_code=201)
def create_staff(
    data: StaffCreateInput,
    actor: dict = Depends(get_current_staff),
):
    result = create_staff_user(
        name=data.name,
        email=data.email,
        password=data.password,
        role=data.role,
        actor_id=actor["id"],
    )
    raise_staff_error(result)
    return result


@router.patch("/{staff_id}")
def patch_staff(
    staff_id: int,
    data: StaffUpdateInput,
    actor: dict = Depends(get_current_staff),
):
    result = update_staff_user(
        staff_id=staff_id,
        updates=data.model_dump(exclude_unset=True),
        actor_id=actor["id"],
    )
    raise_staff_error(result)
    return result
