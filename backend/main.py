from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import JWTAuthMiddleware
from api.routes.auth import router as auth_router

app = FastAPI(title="Moonshoot")

app.add_middleware(JWTAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://moonshoot-gamma.vercel.app", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
