from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional
import uuid
from datetime import datetime, timezone
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================
# CONFIG
# =========================
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get("MONGO_URL")
db_name = os.environ.get("DB_NAME", "hamaca_azul_db")

if not mongo_url:
    raise RuntimeError("MONGO_URL no está configurado")

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

# 👇 IMPORTANTE: habilitar docs
app = FastAPI(
    title="Hamaca Azul API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Router
api_router = APIRouter(prefix="/api")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# MODELOS
# =========================
class ContactCreate(BaseModel):
    email: EmailStr
    description: str = Field(..., max_length=120)
    interest: str

class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    description: str
    interest: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# =========================
# EMAIL CONFIG
# =========================
SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '1025'))
SMTP_USER = os.environ.get('SMTP_USER', 'test@test.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM = os.environ.get('SMTP_FROM', 'hola@hamacaazul.com')

async def send_email(to_email: str, subject: str, body: str):
    try:
        message = MIMEMultipart('alternative')
        message['From'] = SMTP_FROM
        message['To'] = to_email
        message['Subject'] = subject

        html_part = MIMEText(body, 'html')
        message.attach(html_part)

        # SOLO LOG (no envío real)
        logger.info(f"EMAIL → {to_email} | {subject}")

        return True
    except Exception as e:
        logger.error(f"Email error: {str(e)}")
        return False

def get_email_content(interest: str):
    if interest == 'internal_problem':
        return (
            "Let's get you clarity",
            "<p>You chose to look inward.</p>"
        )
    else:
        return (
            "Let's talk exposure",
            "<p>You chose exposure.</p>"
        )

# =========================
# ROUTES
# =========================

# 👇 ESTA ES LA CLAVE (ROOT)
@app.get("/")
async def health():
    return {"status": "ok", "service": "hamaca-azul-api"}

# 👇 API ROOT
@api_router.get("/")
async def api_root():
    return {"message": "Hamaca Azul API funcionando"}

# 👇 CONTACT
@api_router.post("/contact", response_model=Contact)
async def create_contact(input: ContactCreate):
    try:
        contact_obj = Contact(**input.model_dump())

        doc = contact_obj.model_dump()
        doc["timestamp"] = doc["timestamp"].isoformat()

        await db.contacts.insert_one(doc)

        subject, body = get_email_content(input.interest)
        await send_email(input.email, subject, body)

        logger.info(f"Contact created: {input.email} - Interest: {input.interest}")
        return contact_obj

    except Exception as e:
        logger.exception("ERROR REAL:")
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# MIDDLEWARE
# =========================
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    client.close()