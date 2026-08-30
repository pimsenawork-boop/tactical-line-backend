import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration
from supabase import create_client, Client

app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

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
    images: Optional[List[str]] = []
    user_id: str = "Field_Operator"

@app.get("/")
def read_root():
    return {"status": "Tactical Bot Online"}

@app.get("/form", response_class=HTMLResponse)
def get_form():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>TACTICAL SITREP INTERFACE</title>
        <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <style>
            :root {
                --tactical-green: #00ff66;
                --tactical-dark: #0a0e0d;
                --tactical-panel: rgba(12, 20, 16, 0.88);
                --tactical-border: #1f3d2e;
                --hud-cyan: #00e5ff;
                --danger-red: #ff3333;
            }
            * { box-sizing: border-box; }
            body {
                margin: 0;
                padding: 15px;
                font-family: 'Chakra Petch', sans-serif;
                background: linear-gradient(rgba(10, 14, 13, 0.82), rgba(10, 14, 13, 0.92)),
                            url('https://images.unsplash.com/photo-1579829366248-204fe8413f31?auto=format&fit=crop&w=1920&q=80') center/cover fixed no-repeat;
                color: #d1e7dd;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .hud-container {
                width: 100%;
                max-width: 580px;
                background: var(--tactical-panel);
                border: 2px solid var(--tactical-border);
                border-radius: 6px;
                box-shadow: 0 0 25px rgba(0, 255, 102, 0.15), inset 0 0 15px rgba(0, 0, 0, 0.8);
                padding: 20px;
                backdrop-filter: blur(8px);
                position: relative;
            }
            .hud-container::before {
                content: "[ RECON DRONE FEED // LIVE ]";
                position: absolute;
                top: 6px;
                right: 15px;
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                color: var(--tactical-green);
                letter-spacing: 1px;
            }
            .hud-title {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 20px;
                font-weight: 700;
                color: var(--tactical-green);
                border-bottom: 1px solid var(--tactical-border);
                padding-bottom: 10px;
                margin-top: 5px;
                margin-bottom: 15px;
                letter-spacing: 1.5px;
            }
            .grid-2 {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }
            .form-group {
                margin-bottom: 12px;
            }
            label {
                display: block;
                font-size: 13px;
                font-weight: 600;
                color: var(--hud-cyan);
                margin-bottom: 4px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            input, textarea {
                width: 100%;
                background: rgba(4, 10, 7, 0.85);
                border: 1px solid var(--tactical-border);
                border-radius: 4px;
                color: #fff;
                padding: 8px 10px;
                font-family: 'Chakra Petch', sans-serif;
                font-size: 14px;
                transition: border 0.3s, box-shadow 0.3s;
            }
            input:focus, textarea:focus {
                outline: none;
                border-color: var(--tactical-green);
                box-shadow: 0 0 8px rgba(0, 255, 102, 0.4);
            }
            input[readonly] {
                font-family: 'Share Tech Mono', monospace;
                color: #7ee0ad;
                background: rgba(0, 0, 0, 0.6);
            }
            textarea { resize: vertical; }

            /* ส่วนอัปโหลดภาพ */
            .img-grid {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 8px;
                margin-top: 8px;
            }
            .img-slot {
                aspect-ratio: 1 / 1;
                border: 1px dashed var(--tactical-border);
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.4);
                cursor: pointer;
                overflow: hidden;
                position: relative;
            }
            .img-slot img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .img-slot span {
                font-size: 20px;
                color: var(--tactical-border);
            }
            #file_input { display: none; }

            .btn-action {
                width: 100%;
                background: linear-gradient(180deg, #107c41 0%, #0a4d28 100%);
                border: 1px solid var(--tactical-green);
                color: #fff;
                padding: 12px;
                font-size: 16px;
                font-weight: 700;
                letter-spacing: 2px;
                cursor: pointer;
                border-radius: 4px;
                margin-top: 15px;
                text-transform: uppercase;
                box-shadow: 0 0 15px rgba(0, 255, 102, 0.3);
                transition: 0.2s;
            }
            .btn-action:hover {
                background: var(--tactical-green);
                color: #000;
                box-shadow: 0 0 25px rgba(0, 255, 102, 0.6);
            }
            .btn-action:disabled {
                background: #2b3831;
                border-color: #44594e;
                color: #778c80;
                cursor: not-allowed;
                box-shadow: none;
            }
            .status-tag {
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                color: var(--tactical-green);
                margin-top: 3px;
            }
        </style>
    </head>
    <body>
        <div class="hud-container">
            <div class="hud-title">
                <span>🛰️ TACTICAL MISSION REPORT</span>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>🔑 รหัสผ่านยุทธวิธี:</label>
                    <input type="password" id="passcode" placeholder="PASSCODE">
                </div>
                <div class="form-group">
                    <label>1. สถานการณ์:</label>
                    <input type="text" id="situation" placeholder="เช่น การปะทะ / ตรวจพบ">
                </div>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>2. เวลาบันทึก (AUTO):</label>
                    <input type="text" id="time_display" readonly>
                </div>
                <div class="form-group">
                    <label>3. พิกัด GPS (LAT, LON):</label>
                    <input type="text" id="coords_display" readonly placeholder="LOCKING SIGNAL...">
                    <div id="gps_status" class="status-tag">⚡ GPS: ACQUIRING SATELLITE...</div>
                </div>
            </div>

            <div class="form-group">
                <label>4. รายละเอียดเหตุการณ์:</label>
                <textarea id="incident" rows="2" placeholder="ระบุรายละเอียดสิ่งที่ตรวจพบ / รูปแบบเหตุการณ์"></textarea>
            </div>

            <div class="form-group">
                <label>5. การปฏิบัติ / มาตรการตอบโต้:</label>
                <textarea id="action" rows="2" placeholder="ระบุการวางกำลัง / การใช้อาวุธ / การควบคุมพื้นที่"></textarea>
            </div>

            <div class="form-group">
                <label>📷 ภาพถ่ายพื้นที่ปฏิบัติการ (สูงสุด 5 ภาพ):</label>
                <input type="file" id="file_input" accept="image/*" multiple onchange="handleFiles(this.files)">
                <div class="img-grid" onclick="document.getElementById('file_input').click()">
                    <div class="img-slot" id="slot-0"><span>+</span></div>
                    <div class="img-slot" id="slot-1"><span>+</span></div>
                    <div class="img-slot" id="slot-2"><span>+</span></div>
                    <div class="img-slot" id="slot-3"><span>+</span></div>
                    <div class="img-slot" id="slot-4"><span>+</span></div>
                </div>
                <div id="img_count" class="status-tag" style="color: #00e5ff;">ATTACHED: 0 / 5 IMAGES</div>
            </div>

            <button id="submit_btn" class="btn-action" onclick="submitReport()">TRANSMIT REPORT</button>
        </div>

        <script>
            let userLat = 0;
            let userLon = 0;
            let imageBase64List = [];

            function updateTime() {
                const now = new Date();
                document.getElementById('time_display').value = now.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' });
            }
            updateTime();

            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        userLat = pos.coords.latitude;
                        userLon = pos.coords.longitude;
                        document.getElementById('coords_display').value = `${userLat.toFixed(6)}, ${userLon.toFixed(6)}`;
                        document.getElementById('gps_status').innerText = "⚡ GPS: LOCKED & READY";
                    },
                    (err) => {
                        document.getElementById('gps_status').innerText = "⚠️ GPS: MANUAL/OFFLINE";
                        document.getElementById('gps_status').style.color = "#ff3333";
                    },
                    { enableHighAccuracy: true }
                );
            }

            function handleFiles(files) {
                const count = Math.min(files.length, 5);
                imageBase64List = [];
                
                for(let i = 0; i < 5; i++) {
                    const slot = document.getElementById(`slot-${i}`);
                    slot.innerHTML = '<span>+</span>';
                }

                Array.from(files).slice(0, 5).forEach((file, index) => {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        imageBase64List.push(e.target.result);
                        const slot = document.getElementById(`slot-${index}`);
                        slot.innerHTML = `<img src="${e.target.result}">`;
                    };
                    reader.readAsDataURL(file);
                });
                document.getElementById('img_count').innerText = `ATTACHED: ${count} / 5 IMAGES`;
            }

            async function submitReport() {
                const passcode = document.getElementById('passcode').value;
                const situation = document.getElementById('situation').value;
                const incident = document.getElementById('incident').value;
                const action = document.getElementById('action').value;

                if (!passcode) { alert('กรุณากรอกรหัสผ่านความปลอดภัย'); return; }

                const btn = document.getElementById('submit_btn');
                btn.disabled = true;
                btn.innerText = "TRANSMITTING DATA...";

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
                            images: imageBase64List
                        })
                    });

                    const data = await res.json();
                    if (res.ok) {
                        alert(' TRANSMISSION SUCCESS: ข้อมูลบันทึกเรียบร้อย');
                        location.reload();
                    } else {
                        alert('❌ ERROR: ' + data.detail);
                        btn.disabled = false;
                        btn.innerText = "TRANSMIT REPORT";
                    }
                } catch (e) {
                    alert('⚠️ การส่งข้อมูลล้มเหลว กรุณาตรวจสอบการเชื่อมต่อ');
                    btn.disabled = false;
                    btn.innerText = "TRANSMIT REPORT";
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/submit-report")
async def submit_report(payload: ReportPayload):
    if payload.passcode != REPORT_PASSCODE:
        raise HTTPException(status_code=400, detail="รหัสผ่านความปลอดภัยไม่ถูกต้อง!")

    now = datetime.now(THAILAND_TZ)
    time_str = now.strftime("%d/%m/%Y %H:%M:%S")

    try:
        report_data = {
            "user_id": payload.user_id,
            "report_type": "รายงานยุทธวิธี (Tactical HUD)",
            "detail": (
                f"เวลาปฏิบัติการ: {time_str}\n"
                f"1. สถานการณ์: {payload.situation}\n"
                f"3. เหตุการณ์: {payload.incident}\n"
                f"5. การปฏิบัติ: {payload.action}\n"
                f"จำนวนภาพถ่าย: {len(payload.images)} ภาพ"
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
    return Response(content="OK", status_code=200)
