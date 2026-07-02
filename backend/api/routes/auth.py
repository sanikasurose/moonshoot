"""POST /api/auth/verify — password → 30-day JWT (docs/TRD.md section 8)."""
import datetime
import hmac

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import APP_PASSWORD, JWT_SECRET

router = APIRouter()


class VerifyRequest(BaseModel):
    password: str


@router.post("/api/auth/verify")
def verify(body: VerifyRequest):
    if not APP_PASSWORD or not hmac.compare_digest(body.password, APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = jwt.encode(
        {"exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"token": token}
