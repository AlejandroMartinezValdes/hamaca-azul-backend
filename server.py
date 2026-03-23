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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class ContactCreate(BaseModel):
    email: EmailStr
    description: str = Field(..., max_length=120)
    interest: str  # 'internal_problem' or 'influencer_exposure'

class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    description: str
    interest: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Email configuration
SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '1025'))
SMTP_USER = os.environ.get('SMTP_USER', 'test@test.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_FROM = os.environ.get('SMTP_FROM', 'hola@hamacaazul.com')

async def send_email(to_email: str, subject: str, body: str):
    """Send email via SMTP"""
    try:
        message = MIMEMultipart('alternative')
        message['From'] = SMTP_FROM
        message['To'] = to_email
        message['Subject'] = subject

        html_part = MIMEText(body, 'html')
        message.attach(html_part)

        # For development, just log the email
        logger.info(f"\n{'='*60}")
        logger.info(f"EMAIL WOULD BE SENT:")
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body:\n{body}")
        logger.info(f"{'='*60}\n")

        # Uncomment below for actual SMTP sending
        # await aiosmtplib.send(
        #     message,
        #     hostname=SMTP_HOST,
        #     port=SMTP_PORT,
        #     username=SMTP_USER,
        #     password=SMTP_PASSWORD,
        # )
        
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

def get_email_content(interest: str) -> tuple[str, str]:
    """Get email subject and body based on interest"""
    if interest == 'internal_problem':
        subject = "Let's get you clarity"
        body = """
        <html>
            <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                <p>You chose to look inward. Here's our profile.</p>
                <p>Now tell us in one sentence: what is your brand missing — clarity, identity, or direction?</p>
                <br>
                <p style="color: #666; font-size: 12px;">Hamaca Azul — CDMX</p>
            </body>
        </html>
        """
    else:  # influencer_exposure
        subject = "Let's talk exposure that works"
        body = """
        <html>
            <body style="font-family: sans-serif; line-height: 1.6; color: #333;">
                <p>You chose intentional exposure. Here's our profile.</p>
                <p>Now tell us in one sentence: what result do you want to achieve with influencers?</p>
                <br>
                <p style="color: #666; font-size: 12px;">Hamaca Azul — CDMX</p>
            </body>
        </html>
        """
    return subject, body

# Routes
@api_router.get("/")
async def root():
    return {"message": "Hamaca Azul API"}

@api_router.post("/contact", response_model=Contact)
async def create_contact(input: ContactCreate):
    """Create contact and send email"""
    try:
        # Create contact object
        contact_obj = Contact(**input.model_dump())
        
        # Convert to dict and serialize datetime
        doc = contact_obj.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        
        # Save to MongoDB
        await db.contacts.insert_one(doc)
        
        # Send email
        subject, body = get_email_content(input.interest)
        await send_email(input.email, subject, body)
        
        logger.info(f"Contact created: {input.email} - Interest: {input.interest}")
        
        return contact_obj
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing request")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()