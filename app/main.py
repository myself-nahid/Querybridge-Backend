from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, Base
from app.api.v1 import auth, chat, users, admin

# Create Database Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="QueryBridge AI Backend",
    description="Core API Gateway handling Auth, Users, and routing to AI Microservice.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GLOBAL EXCEPTION HANDLERS
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Formats manual HTTPExceptions into the Standard Response"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": str(exc.detail), "data": None}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Formats Pydantic payload validation errors into the Standard Response"""
    errors = exc.errors()
    error_msg = "Validation Error"
    if len(errors) > 0:
        # Extract the first error message for the main message string
        error_msg = f"{errors[0]['loc'][-1]}: {errors[0]['msg']}"
        
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": error_msg, "data": errors}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Formats unhandled 500 server errors into the Standard Response"""
    # Note: Do not expose `str(exc)` in a real production app to avoid leaking system info
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal Server Error", "data": str(exc)}
    )

# STATIC FILES (for user avatars)
app.mount("/api/v1/avatars", StaticFiles(directory="uploads/avatars"), name="avatars")

# ROUTERS
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["User Management"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin Dashboard"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI Chat Portal"])

@app.get("/")
def root():
    return {"success": True, "message": "QueryBridge AI API is running!", "data": None}