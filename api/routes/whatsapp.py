
import os
import traceback

from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse

from api.services.whatsapp_service import send_whatsapp_message
from main import run_agent

load_dotenv()

router = APIRouter()
MAX_MESSAGE_LENGTH = 2000



@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    data = await request.json()

    print("\n========== WEBHOOK RECEIVED ==========")
    print("Payload:", data)

    background_tasks.add_task(
        process_whatsapp_message,
        data,
    )

    return {"status": "received"}



async def process_whatsapp_message(data: dict):
    try:
        entries = data.get("entry", [])

        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                # Ignore delivery receipts and status events
                for message in messages:
                    if message.get("type") != "text":
                        continue

                    from_number = message.get("from")
                    user_text = message.get(
                        "text", {}
                    ).get("body", "").strip()

                    if not from_number or not user_text:
                        continue

                    if len(user_text) > MAX_MESSAGE_LENGTH:
                        await send_whatsapp_message(
                            to=from_number,
                            body=(
                                "Your message is too long. "
                                "Please send a shorter message."
                            ),
                        )
                        continue

                    try:
                        response = await run_agent(
                            user_text,
                            from_number,
                        )

                        # Ensure we send text, not a Python dict
                        if not isinstance(response, str):
                            response = str(response)

                        await send_whatsapp_message(
                            to=from_number,
                            body=response,
                        )

                    except Exception as exc:
                        print(
                            "Agent/WhatsApp processing failed:",
                            type(exc).__name__,
                            str(exc),
                        )
                        traceback.print_exc()

                        try:
                            await send_whatsapp_message(
                                to=from_number,
                                body=(
                                    "Sorry, our AI assistant is "
                                    "temporarily unavailable. "
                                    "Please try again shortly."
                                ),
                            )
                        except Exception:
                            traceback.print_exc()

        return {"status": "processed"}

    except Exception:
        traceback.print_exc()
        return {"status": "processing_failed"}


@router.get(
    "/webhook",
    response_class=PlainTextResponse,
)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(
        None, alias="hub.verify_token"
    ),
    hub_challenge: str = Query(
        None, alias="hub.challenge"
    ),
):
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")

    if (
        hub_mode == "subscribe"
        and verify_token
        and hub_verify_token == verify_token
        and hub_challenge is not None
    ):
        return hub_challenge

    raise HTTPException(
        status_code=403,
        detail="Verification failed",
    )
