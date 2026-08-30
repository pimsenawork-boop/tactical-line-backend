import os
from fastapi import FastAPI, Request, HTTPException, Response
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    LocationMessageContent
)
from supabase import create_client, Client

app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
def read_root():
    return {"status": "Tactical Bot is running"}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")
    
    # รองรับการกด Verify จาก LINE Developers
    if not signature or not body_text:
        return Response(content="OK", status_code=200)

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        return Response(content="OK", status_code=200)
    except Exception as e:
        print(f"Error: {e}")
        return Response(content="OK", status_code=200)
        
    return Response(content="OK", status_code=200)

@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location(event):
    lat = event.message.latitude
    lon = event.message.longitude
    address = event.message.address or "ไม่ระบุตำแหน่ง"
    user_id = event.source.user_id

    try:
        data = {
            "user_id": user_id,
            "detail": f"พิกัดสถานที่: {address}",
            "latitude": lat,
            "longitude": lon,
            "report_type": "แจ้งพิกัดยุทธวิธี"
        }
        supabase.table("reports").insert(data).execute()
    except Exception as err:
        print(f"Supabase Error: {err}")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        reply_text = f"📍 บันทึกพิกัดสำเร็จ!\nละติจูด: {lat}\nลองจิจูด: {lon}\nสถานที่: {address}"
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )
