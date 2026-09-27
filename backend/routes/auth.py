from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import (
    authenticate_staff,
    create_access_token,
    get_current_staff,
)


router = APIRouter(prefix="/api/auth", tags=["Staff Authentication"])


class LoginInput(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(data: LoginInput):
    staff = authenticate_staff(data.email, data.password)
    if staff is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_in = create_access_token(staff)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "staff": staff,
    }


@router.get("/me")
def get_current_staff_profile(staff: dict = Depends(get_current_staff)):
    return {"staff": staff}
