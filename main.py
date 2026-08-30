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
    user_id: str = "PHANTOM_OPERATOR"

@app.get("/")
def read_root():
    return {"status": "Tactical PHANTOM System Active"}

@app.get("/form", response_class=HTMLResponse)
def get_form():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>PHANTOM TACTICAL SITREP</title>
        <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:ital,wght@0,300;0,400;0,600;0,700;1,400&family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <style>
            :root {
                --gold-accent: #d4af37;
                --gold-glow: rgba(212, 175, 55, 0.45);
                --panel-bg: rgba(12, 17, 14, 0.85);
                --input-bg: rgba(6, 10, 8, 0.75);
                --border-subtle: rgba(212, 175, 55, 0.35);
                --thai-red: #a51c24;
                --thai-blue: #1c2c59;
            }
            * { box-sizing: border-box; }
            body {
                margin: 0;
                padding: 15px;
                font-family: 'Chakra Petch', sans-serif;
                background-color: #0b0e0c;
                /* พื้นหลังลวดลายเส้นใยผ้าสนาม Tactical Cordura ผสมแสงตกกระทบ */
                background-image: 
                    radial-gradient(circle at 50% 15%, rgba(212, 175, 55, 0.18) 0%, transparent 60%),
                    radial-gradient(circle at 50% 85%, rgba(0, 0, 0, 0.8) 0%, transparent 70%),
                    linear-gradient(45deg, #0e1411 25%, transparent 25%), 
                    linear-gradient(-45deg, #0e1411 25%, transparent 25%), 
                    linear-gradient(45deg, transparent 75%, #0e1411 75%), 
                    linear-gradient(-45deg, transparent 75%, #0e1411 75%);
                background-size: 100% 100%, 100% 100%, 12px 12px, 12px 12px, 12px 12px, 12px 12px;
                background-position: center, center, 0 0, 0 6px, 6px -6px, -6px 0px;
                color: #e2e8e5;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .hud-container {
                width: 100%;
                max-width: 520px;
                background: var(--panel-bg);
                border: 1px solid var(--border-subtle);
                border-radius: 12px;
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.9), 0 0 25px rgba(212, 175, 55, 0.15);
                padding: 22px 20px;
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                position: relative;
                overflow: hidden;
            }
            .thai-ribbon {
                position: absolute;
                top: 0;
                right: 0;
                width: 70px;
                height: 5px;
                background: linear-gradient(90deg, 
                    var(--thai-red) 0% 20%, 
                    #fff 20% 40%, 
                    var(--thai-blue) 40% 60%, 
                    #fff 60% 80%, 
                    var(--thai-red) 80% 100%);
                box-shadow: 0 0 8px rgba(255, 255, 255, 0.3);
            }
            .header-badge {
                text-align: center;
                margin-bottom: 16px;
                position: relative;
            }
            .patch-container {
                width: 85px;
                height: 85px;
                margin: 0 auto 10px auto;
                background: radial-gradient(circle, rgba(212, 175, 55, 0.25) 0%, rgba(0,0,0,0) 70%);
                display: flex;
                align-items: center;
                justify-content: center;
                filter: drop-shadow(0 0 10px rgba(212, 175, 55, 0.3));
            }
            .patch-svg {
                width: 75px;
                height: 75px;
            }
            .title-main {
                font-size: 20px;
                font-weight: 700;
                color: var(--gold-accent);
                letter-spacing: 2px;
                text-transform: uppercase;
                margin: 0;
                text-shadow: 0 2px 5px rgba(0, 0, 0, 0.9);
            }
            .title-sub {
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                color: #8b9b92;
                letter-spacing: 1px;
            }
            .grid-2 {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            .form-group {
                margin-bottom: 12px;
            }
            label {
                display: block;
                font-size: 12px;
                font-weight: 600;
                color: #9cb1a5;
                margin-bottom: 4px;
                letter-spacing: 0.5px;
            }
            input, textarea {
                width: 100%;
                background: var(--input-bg);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 7px;
                color: #ffffff;
                padding: 9px 12px;
                font-family: 'Chakra Petch', sans-serif;
                font-size: 13.5px;
                transition: all 0.25s ease;
            }
            input:focus, textarea:focus {
                outline: none;
                border-color: var(--gold-accent);
                background: rgba(12, 18, 14, 0.92);
                box-shadow: 0 0 10px var(--gold-glow);
            }
            input[readonly] {
                font-family: 'Share Tech Mono', monospace;
                color: #a8d5be;
                background: rgba(0, 0, 0, 0.5);
                border-color: rgba(255, 255, 255, 0.05);
            }
            textarea { resize: vertical; min-height: 52px; }

            .img-grid {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 8px;
                margin-top: 6px;
            }
            .img-slot {
                aspect-ratio: 1 / 1;
                border: 1px dashed rgba(212, 175, 55, 0.4);
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.4);
                cursor: pointer;
                overflow: hidden;
                position: relative;
                transition: 0.2s;
            }
            .img-slot:hover {
                border-color: var(--gold-accent);
                background: rgba(212, 175, 55, 0.1);
            }
            .img-slot img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .img-slot span {
                font-size: 18px;
                color: rgba(212, 175, 55, 0.7);
            }
            #file_input { display: none; }

            .btn-action {
                width: 100%;
                background: linear-gradient(135deg, #a88424 0%, #614a10 100%);
                border: 1px solid var(--gold-accent);
                color: #fff;
                padding: 11px;
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 2px;
                cursor: pointer;
                border-radius: 7px;
                margin-top: 14px;
                text-transform: uppercase;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
                transition: all 0.25s ease;
            }
            .btn-action:hover {
                background: linear-gradient(135deg, #c49d32 0%, #7d6017 100%);
                box-shadow: 0 0 16px var(--gold-glow);
                transform: translateY(-1px);
            }
            .btn-action:disabled {
                background: #252826;
                border-color: #3b403d;
                color: #6a736e;
                cursor: not-allowed;
                box-shadow: none;
                transform: none;
            }
            .status-tag {
                font-family: 'Share Tech Mono', monospace;
                font-size: 10.5px;
                color: #9cb1a5;
                margin-top: 3px;
            }
        </style>
    </head>
    <body>
        <div class="hud-container">
            <div class="thai-ribbon"></div>
            
            <div class="header-badge">
                <div class="patch-container">
                    <!-- SVG สัญลักษณ์อินทรีทอง PHANTOM คมชัดระดับ Vector -->
                    <svg class="patch-svg" viewBox="0 0 100 100">
                        <polygon points="50,5 95,30 80,95 20,95 5,30" fill="#2d3b2b" stroke="#d4af37" stroke-width="3" />
                        <polygon points="50,12 88,33 75,88 25,88 12,33" fill="#1b241a" stroke="#d4af37" stroke-width="1" />
                        <!-- ปีกนก -->
                        <path d="M50 35 L75 25 L85 45 L65 50 L50 65 L35 50 L15 45 L25 25 Z" fill="#c49d32" />
                        <!-- หัวอินทรี & ตาแดง -->
                        <circle cx="50" cy="40" r="10" fill="#e5c158" />
                        <circle cx="46" cy="38" r="2" fill="#ff1a1a" />
                        <circle cx="54" cy="38" r="2" fill="#ff1a1a" />
                        <polygon points="50,42 47,48 53,48" fill="#d4af37" />
                        <!-- แท่นชื่อ PHANTOM -->
                        <rect x="25" y="70" width="50" height="14" fill="#000" stroke="#d4af37" stroke-width="1" rx="2" />
                        <text x="50" y="81" font-family="'Chakra Petch', sans-serif" font-size="8" font-weight="bold" fill="#d4af37" text-anchor="middle">PHANTOM</text>
                    </svg>
                </div>
                <h1 class="title-main">PHANTOM SITREP</h1>
                <div class="title-sub">ROYAL THAI TACTICAL UNIT // RECON FEED</div>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>🔑 รหัสผ่าน (Passcode):</label>
                    <input type="password" id="passcode" placeholder="กรอกรหัส">
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
                    <input type="text" id="coords_display" readonly placeholder="จับสัญญาณดาวเทียม...">
                    <div id="gps_status" class="status-tag">⚡ GPS: ค้นหาพิกัด...</div>
                </div>
            </div>

            <div class="form-group">
                <label>4. เหตุการณ์:</label>
                <textarea id="incident" rows="2" placeholder="ระบุรายละเอียดสิ่งที่ตรวจพบ / รูปแบบเหตุการณ์"></textarea>
            </div>

            <div class="form-group">
                <label>5. การปฏิบัติ:</label>
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
                <div id="img_count" class="status-tag">แนบภาพ: 0 / 5 ภาพ</div>
            </div>

            <button id="submit_btn" class="btn-action" onclick="submitReport()">ส่งรายงานยุทธวิธี</button>
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
                        document.getElementById('gps_status').innerText = "⚡ GPS: พิกัดพร้อมส่ง";
                        document.getElementById('gps_status').style.color = "#d4af37";
                    },
                    (err) => {
                        document.getElementById('gps_status').innerText = "⚠️ GPS: ออฟไลน์ / กำหนดเอง";
                        document.getElementById('gps_status').style.color = "#e57373";
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
                document.getElementById('img_count').innerText = `แนบภาพ: ${count} / 5 ภาพ`;
            }

            async function submitReport() {
                const passcode = document.getElementById('passcode').value;
                const situation = document.getElementById('situation').value;
                const incident = document.getElementById('incident').value;
                const action = document.getElementById('action').value;

                if (!passcode) { alert('กรุณากรอกรหัสผ่านความปลอดภัย'); return; }

                const btn = document.getElementById('submit_btn');
                btn.disabled = true;
                btn.innerText = "กำลังส่งข้อมูล...";

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
                        alert('✅ บันทึกรายงานเข้าสู่ระบบสำเร็จ');
                        location.reload();
                    } else {
                        alert('❌ ' + data.detail);
                        btn.disabled = false;
                        btn.innerText = "ส่งรายงานยุทธวิธี";
                    }
                } catch (e) {
                    alert('⚠️ การส่งข้อมูลล้มเหลว กรุณาตรวจสอบการเชื่อมต่อ');
                    btn.disabled = false;
                    btn.innerText = "ส่งรายงานยุทธวิธี";
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
            "report_type": "รายงานยุทธวิธี (PHANTOM HUD)",
            "detail": (
                f"เวลา: {time_str}\n"
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
