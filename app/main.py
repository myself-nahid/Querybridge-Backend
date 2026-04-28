import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import async_engine, Base
from app.api.v1 import auth, chat, users, admin

app = FastAPI(
    title="QueryBridge AI Backend",
    description="Core API Gateway handling Auth, Users, and routing to AI Microservice.",
    version="1.0.0"
)

# ASYNC DATABASE CREATION 
@app.on_event("startup")
async def startup_event():
    """Creates database tables asynchronously on startup."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

CORS = ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": str(exc.detail), "data": None})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_msg = f"{errors[0]['loc'][-1]}: {errors[0]['msg']}" if len(errors) > 0 else "Validation Error"
    return JSONResponse(status_code=422, content={"success": False, "message": error_msg, "data": errors})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"success": False, "message": "Internal Server Error", "data": str(exc)})

os.makedirs("uploads/avatars", exist_ok=True)
app.mount("/api/v1/avatars", StaticFiles(directory="uploads/avatars"), name="avatars")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["User Management"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin Dashboard"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI Chat Portal"])

@app.get("/")
def root():
    return {"success": True, "message": "QueryBridge AI API is running!", "data": None}