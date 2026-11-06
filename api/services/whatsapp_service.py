import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")



import httpx

async def send_whatsapp_message(to: str, body: str):
    """Send a text message using WhatsApp Cloud API."""

    url = (
        f"https://graph.facebook.com/v26.0/"
        f"{PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": body,
        },
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
        )

    if response.is_error:
        print("WhatsApp API error:", response.text)
        response.raise_for_status()

    print("WhatsApp reply sent:", response.json())
    return response.json()
