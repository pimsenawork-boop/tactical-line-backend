import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from supabase import create_client, Client

app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# รหัสผ่านความปลอดภัย
REPORT_PASSCODE = "phantom2"

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

THAILAND_TZ = timezone(timedelta(hours=7))

class ReportPayload(BaseModel):
    passcode: str
    situation: str
    incident: str
    action: str
    latitude: float
    longitude: float
    user_id: str = "Anonymous"

@app.get("/")
def read_root():
    return {"status": "Tactical Bot is running"}

# หน้าเว็บฟอร์มกรอกข้อมูลพร้อมดึง GPS อัตโนมัติ
@app.get("/form", response_class=HTMLResponse)
def get_form():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ระบบรายงานทางยุทธวิธี</title>
        <script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #fff; padding: 15px; margin: 0; }
            .card { background: #1e1e1e; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
            h2 { text-align: center; color: #00c300; margin-top: 0; }
            label { display: block; margin-top: 12px; font-weight: bold; font-size: 14px; }
            input, textarea { width: 100%; padding: 10px; margin-top: 5px; border-radius: 6px; border: 1px solid #333; background: #2a2a2a; color: #fff; box-sizing: border-box; font-size: 15px; }
            input[readonly] { background: #1a1a1a; color: #888; }
            button { width: 100%; padding: 12px; margin-top: 20px; background-color: #00c300; border: none; border-radius: 6px; color: white; font-weight: bold; font-size: 16px; cursor: pointer; }
            button:disabled { background-color: #555; }
            .gps-status { font-size: 13px; color: #00ffc4; margin-top: 4px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2> แบบรายงานยุทธวิธี</h2>
            
            <label>🔑 รหัสผ่านความปลอดภัย (Passcode):</label>
            <input type="password" id="passcode" placeholder="กรอกรหัสผ่าน">

            <label>1. สถานการณ์:</label>
            <input type="text" id="situation" placeholder="เช่น การตรวจพบความเคลื่อนไหว">

            <label>2. เวลาบันทึก (อัตโนมัติ):</label>
            <input type="text" id="time_display" readonly>

            <label>3. พิกัด GPS (ดึงอัตโนมัติ):</label>
            <input type="text" id="coords_display" readonly placeholder="กำลังจับสัญญาณ GPS...">
            <div id="gps_status" class="gps-status"> กำลังระบุตำแหน่ง...</div>

            <label>4. เหตุการณ์:</label>
            <textarea id="incident" rows="3" placeholder="ระบุรายละเอียดเหตุการณ์"></textarea>

            <label>5. การปฏิบัติ:</label>
            <textarea id="action" rows="3" placeholder="ระบุการปฏิบัติ/มาตรการ"></textarea>

            <button id="submit_btn" onclick="submitReport()"> ส่งรายงานทันที</button>
        </div>

        <script>
            let userLat = 0;
            let userLon = 0;
            let lineUserId = "Unknown";

            // อัปเดตเวลาไทยอัตโนมัติ
            function updateTime() {
                const now = new Date();
                document.getElementById('time_display').value = now.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' });
            }
            updateTime();

            // ดึงพิกัด GPS อัตโนมัติจากโทรศัพท์
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        userLat = position.coords.latitude;
                        userLon = position.coords.longitude;
                        document.getElementById('coords_display').value = `${userLat.toFixed(6)}, ${userLon.toFixed(6)}`;
                        document.getElementById('gps_status').innerText = " พิกัดพร้อมส่ง";
                    },
                    (error) => {
                        document.getElementById('gps_status').innerText = "⚠️ ไม่สามารถดึง GPS ได้ (กรุณาเปิดตำแหน่งที่ตั้ง)";
                    },
                    { enableHighAccuracy: true }
                );
            }

            // เริ่มต้นระบบ LIFF เพื่อดึง ID ผู้ใช้
            async function main() {
                await liff.init({ liffId: "LIFF_INIT_PLACEHOLDER" });
                if (liff.isLoggedIn()) {
                    const profile = await liff.getProfile();
                    lineUserId = profile.userId;
                }
            }
            main();

            async function submitReport() {
                const passcode = document.getElementById('passcode').value;
                const situation = document.getElementById('situation').value;
                const incident = document.getElementById('incident').value;
                const action = document.getElementById('action').value;

                if (!passcode) { alert('กรุณากรอกรหัสผ่าน'); return; }
                if (userLat === 0 && userLon === 0) {
                    if (!confirm('ยังไม่สามารถดึงพิกัด GPS ได้ ต้องการส่งข้อมูลต่อหรือไม่?')) return;
                }

                const btn = document.getElementById('submit_btn');
                btn.disabled = true;
                btn.innerText = "กำลังบันทึกข้อมูล...";

                try {
                    const res = await fetch('/api/submit-report', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            passcode: passcode,
                            situation: situation,
                            incident: incident,
                            action: action,
                            latitude: userLat,
                            longitude: userLon,
                            user_id: lineUserId
                        })
                    });

                    const data = await res.json();
                    if (res.ok) {
                        alert('✅ ส่งรายงานสำเร็จเรียบร้อย!');
                        if (liff.isInClient()) {
                            liff.closeWindow();
                        }
                    } else {
                        alert('❌ ' + data.detail);
                        btn.disabled = false;
                        btn.innerText = "🚀 ส่งรายงานทันที";
                    }
                } catch (e) {
                    alert('⚠️ การเชื่อมต่อล้มเหลว กรุณาลองใหม่อีกครั้ง');
                    btn.disabled = false;
                    btn.innerText = "🚀 ส่งรายงานทันที";
                }
            }
        </script>
    </body>
    </html>
    """

# API รับข้อมูลจากฟอร์ม บันทึกเข้า Supabase
@app.post("/api/submit-report")
async def submit_report(payload: ReportPayload):
    if payload.passcode != REPORT_PASSCODE:
        raise HTTPException(status_code=400, detail="รหัสผ่านไม่ถูกต้อง!")

    now = datetime.now(THAILAND_TZ)
    time_str = now.strftime("%d/%m/%Y %H:%M:%S")

    # บันทึกลง Supabase
    try:
        report_data = {
            "user_id": payload.user_id,
            "report_type": "รายงานยุทธวิธี (ผ่านฟอร์ม)",
            "detail": (
                f"เวลา: {time_str}\n"
                f"1. สถานการณ์: {payload.situation}\n"
                f"2. เหตุการณ์: {payload.incident}\n"
                f"3. การปฏิบัติ: {payload.action}"
            ),
            "latitude": payload.latitude,
            "longitude": payload.longitude
        }
        supabase.table("reports").insert(report_data).execute()
    except Exception as err:
        print(f"Supabase error: {err}")
        raise HTTPException(status_code=500, detail="ไม่สามารถบันทึกข้อมูลลงฐานข้อมูลได้")

    return {"status": "success", "time": time_str}

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")
    if not signature or not body_text:
        return Response(content="OK", status_code=200)
    try:
        handler.handle(body_text, signature)
    except Exception:
        return Response(content="OK", status_code=200)
    return Response(content="OK", status_code=200)
