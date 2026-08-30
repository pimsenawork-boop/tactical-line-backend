import os
import uuid
import base64
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse
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
ADMIN_MAP_PASSCODE = "phantomadmin"

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
    mgrs: Optional[str] = ""
    tactical_icon: Optional[str] = "🎯 ตรวจพบเป้าหมาย"
    images: Optional[List[str]] = []
    user_id: str = "PHANTOM_OPERATOR"

@app.get("/")
def read_root():
    return {"status": "Tactical PHANTOM System Active", "form_url": "/form", "map_view": "/map"}

@app.get("/bg.jpg")
def get_old_background_image():
    if os.path.exists("bg.jpg"):
        return FileResponse("bg.jpg")
    return Response(status_code=404)

@app.get("/bg_new.jpg")
def get_new_background_image():
    if os.path.exists("bg_new.jpg"):
        return FileResponse("bg_new.jpg")
    return Response(status_code=404)

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
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            :root {
                --gold-accent: #d4af37;
                --gold-light: #f5d77f;
                --gold-glow: rgba(212, 175, 55, 0.45);
                --border-subtle: rgba(212, 175, 55, 0.25);
                --thai-red: #d32f2f;
                --thai-blue: #1976d2;
                --mgrs-green: #00ffcc;
                --cyan-glow: rgba(0, 255, 204, 0.35);
                --card-bg: rgba(10, 16, 13, 0.88);
            }
            * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
            
            body {
                margin: 0;
                padding: 16px 12px;
                font-family: 'Chakra Petch', sans-serif;
                background-color: #050806;
                background-image: 
                    radial-gradient(circle at 50% 0%, rgba(212, 175, 55, 0.08) 0%, transparent 75%),
                    linear-gradient(rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0.85)),
                    url('/bg_new.jpg');
                background-size: cover;
                background-position: center center;
                background-repeat: no-repeat;
                background-attachment: fixed;
                color: #e2e8e5;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }

            .hud-container {
                width: 100%;
                max-width: 500px;
                background: var(--card-bg);
                backdrop-filter: blur(18px);
                -webkit-backdrop-filter: blur(18px);
                border: 1px solid var(--border-subtle);
                border-radius: 18px;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.9), 0 0 30px rgba(212, 175, 55, 0.12);
                padding: 24px 20px;
                position: relative;
                overflow: hidden;
            }

            /* สัญลักษณ์ริบบิ้นธงชาติไทยมุมบน */
            .thai-ribbon {
                position: absolute;
                top: 0;
                right: 0;
                width: 90px;
                height: 4px;
                background: linear-gradient(90deg, 
                    var(--thai-red) 0% 20%, 
                    #fff 20% 40%, 
                    var(--thai-blue) 40% 60%, 
                    #fff 60% 80%, 
                    var(--thai-red) 80% 100%);
            }

            .header-badge {
                text-align: center;
                margin-bottom: 20px;
                position: relative;
            }
            .header-badge::after {
                content: '';
                display: block;
                width: 60px;
                height: 2px;
                background: linear-gradient(90deg, transparent, var(--gold-accent), transparent);
                margin: 8px auto 0 auto;
            }

            .title-main {
                font-size: 22px;
                font-weight: 700;
                color: var(--gold-accent);
                letter-spacing: 3px;
                text-transform: uppercase;
                margin: 0;
                text-shadow: 0 0 12px var(--gold-glow);
            }
            .title-sub {
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                color: #8da196;
                letter-spacing: 1.5px;
                margin-top: 4px;
            }

            .grid-2 {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }
            .form-group {
                margin-bottom: 14px;
            }
            label {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 12.5px;
                font-weight: 600;
                color: #b0c2b7;
                margin-bottom: 6px;
                letter-spacing: 0.5px;
            }

            /* อินพุตสไตล์ Tactical Glass */
            input, textarea, select {
                width: 100%;
                background: rgba(8, 14, 10, 0.75);
                border: 1px solid rgba(212, 175, 55, 0.25);
                border-radius: 10px;
                color: #ffffff;
                padding: 11px 14px;
                font-family: 'Chakra Petch', sans-serif;
                font-size: 14px;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.4);
            }
            input:focus, textarea:focus, select:focus {
                outline: none;
                border-color: var(--gold-accent);
                background: rgba(12, 20, 15, 0.9);
                box-shadow: 0 0 15px var(--gold-glow), inset 0 2px 4px rgba(0,0,0,0.5);
                transform: translateY(-1px);
            }
            .readonly-input {
                font-family: 'Share Tech Mono', monospace;
                color: #7ee0ad !important;
                background: rgba(4, 8, 6, 0.85);
                border-color: rgba(255, 255, 255, 0.08);
            }
            .mgrs-input {
                font-family: 'Share Tech Mono', monospace;
                color: var(--mgrs-green) !important;
                font-weight: 700;
                letter-spacing: 1.2px;
                background: rgba(0, 20, 15, 0.75);
                border-color: rgba(0, 255, 204, 0.35);
                box-shadow: inset 0 0 8px rgba(0, 255, 204, 0.1);
            }
            textarea { resize: vertical; min-height: 60px; }

            /* สไตล์แถบปุ่มควบคุม Tactical Tools (3 ปุ่มหลัก) */
            .gps-tools {
                display: grid;
                grid-template-columns: 1fr 1.2fr 1fr;
                gap: 8px;
                margin-top: 8px;
            }
            .tool-btn {
                background: linear-gradient(180deg, rgba(25, 38, 30, 0.9) 0%, rgba(12, 20, 15, 0.9) 100%);
                border: 1px solid rgba(212, 175, 55, 0.35);
                color: var(--gold-accent);
                padding: 10px 8px;
                font-size: 11.5px;
                font-weight: 600;
                border-radius: 9px;
                cursor: pointer;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                text-align: center;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 3px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.4);
            }
            .tool-btn:hover {
                border-color: var(--gold-accent);
                box-shadow: 0 0 12px var(--gold-glow);
                transform: translateY(-2px);
                color: #fff;
            }
            .tool-btn:active {
                transform: scale(0.95);
                box-shadow: inset 0 2px 6px rgba(0,0,0,0.6);
            }
            .tool-btn.primary-map {
                border-color: var(--gold-accent);
                background: linear-gradient(180deg, rgba(212, 175, 55, 0.25) 0%, rgba(150, 120, 30, 0.2) 100%);
                color: var(--gold-light);
            }
            .tool-btn.radar-btn {
                border-color: rgba(0, 255, 204, 0.4);
                color: var(--mgrs-green);
                background: linear-gradient(180deg, rgba(0, 255, 204, 0.15) 0%, rgba(0, 100, 80, 0.2) 100%);
            }

            .status-tag {
                font-family: 'Share Tech Mono', monospace;
                font-size: 11.5px;
                color: #8da196;
                margin-top: 6px;
                display: flex;
                align-items: center;
                gap: 5px;
            }

            /* --- MODERN MAP MODAL INTERFACE --- */
            #map-modal {
                display: none;
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.82);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                z-index: 10000;
                opacity: 0;
                transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            }
            #map-modal.show {
                display: flex;
                opacity: 1;
            }
            .map-app-container {
                position: relative;
                width: 100%;
                height: 100%;
                display: flex;
                flex-direction: column;
            }
            #tactical-map {
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                width: 100%; height: 100%;
                z-index: 1;
            }

            .map-top-bar {
                position: absolute;
                top: 15px;
                left: 15px;
                right: 15px;
                z-index: 1000;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .map-top-row {
                display: flex;
                gap: 8px;
            }
            .search-box-wrapper {
                flex: 1;
                background: rgba(14, 20, 16, 0.92);
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                border: 1px solid rgba(212, 175, 55, 0.4);
                border-radius: 30px;
                display: flex;
                align-items: center;
                padding: 4px 16px;
                box-shadow: 0 6px 25px rgba(0,0,0,0.6);
            }
            .search-box-wrapper input {
                background: transparent;
                border: none;
                box-shadow: none;
                padding: 8px 6px;
                font-size: 14px;
                color: #fff;
            }
            .search-box-wrapper input:focus {
                background: transparent;
                box-shadow: none;
                border: none;
            }
            .btn-circle-icon {
                width: 46px;
                height: 46px;
                border-radius: 50%;
                background: rgba(14, 20, 16, 0.92);
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                border: 1px solid rgba(212, 175, 55, 0.4);
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                cursor: pointer;
                box-shadow: 0 6px 20px rgba(0,0,0,0.6);
                transition: 0.2s;
            }
            .btn-circle-icon:active { transform: scale(0.92); }

            .provider-selector-bar {
                background: rgba(14, 20, 16, 0.92);
                backdrop-filter: blur(14px);
                border: 1px solid rgba(212, 175, 55, 0.35);
                border-radius: 12px;
                padding: 5px 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.6);
            }
            .provider-selector-bar select {
                background: transparent;
                border: none;
                color: var(--gold-accent);
                font-size: 13px;
                font-weight: 600;
                padding: 4px;
                cursor: pointer;
            }

            .map-floating-controls {
                position: absolute;
                right: 15px;
                bottom: 155px;
                z-index: 1000;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .center-pin-marker {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -100%);
                z-index: 100;
                pointer-events: none;
                transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1);
                text-align: center;
            }
            .center-pin-marker.dragging {
                transform: translate(-50%, -125%) scale(1.15);
            }
            .pin-emoji-badge {
                font-size: 36px;
                filter: drop-shadow(0 6px 12px rgba(0,0,0,0.9));
            }
            .pin-shadow {
                position: absolute;
                bottom: -2px;
                left: 50%;
                transform: translateX(-50%);
                width: 16px;
                height: 6px;
                background: rgba(0,0,0,0.7);
                border-radius: 50%;
                filter: blur(1.5px);
            }

            .map-bottom-sheet {
                position: absolute;
                bottom: 16px;
                left: 15px;
                right: 15px;
                z-index: 1000;
                background: rgba(10, 16, 13, 0.95);
                backdrop-filter: blur(18px);
                -webkit-backdrop-filter: blur(18px);
                border: 1.5px solid var(--border-subtle);
                border-radius: 18px;
                padding: 16px 18px;
                box-shadow: 0 12px 35px rgba(0,0,0,0.85);
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
            }
            .coord-info-title {
                font-size: 11px;
                color: #8da196;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .coord-info-val {
                font-family: 'Share Tech Mono', monospace;
                font-size: 13.5px;
                font-weight: 700;
                color: #7ee0ad;
                margin-top: 2px;
            }
            .coord-mgrs-val {
                font-family: 'Share Tech Mono', monospace;
                font-size: 13.5px;
                font-weight: 700;
                color: var(--mgrs-green);
                margin-top: 1px;
            }
            .btn-confirm-pin {
                background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%);
                border: 1px solid var(--gold-accent);
                color: #000;
                font-weight: 700;
                font-size: 13px;
                padding: 12px 20px;
                border-radius: 12px;
                cursor: pointer;
                text-transform: uppercase;
                letter-spacing: 1px;
                box-shadow: 0 4px 15px rgba(212, 175, 55, 0.35);
                white-space: nowrap;
                transition: 0.2s;
            }
            .btn-confirm-pin:active { transform: scale(0.95); }

            /* 5 ช่องสี่เหลี่ยมแนบภาพดีไซน์ใหม่ */
            .img-grid {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 8px;
                margin-top: 8px;
            }
            .img-slot {
                aspect-ratio: 1 / 1;
                background: rgba(8, 14, 10, 0.75);
                border: 1.5px dashed rgba(212, 175, 55, 0.35);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                overflow: hidden;
                position: relative;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .img-slot:hover {
                border-color: var(--gold-accent);
                box-shadow: 0 0 12px var(--gold-glow);
                transform: translateY(-2px);
            }
            .img-slot img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .img-slot span {
                font-size: 22px;
                color: var(--gold-accent);
                font-weight: 300;
            }
            .btn-remove-img {
                position: absolute;
                top: 3px;
                right: 3px;
                background: rgba(211, 47, 47, 0.92);
                color: #fff;
                border: 1px solid #fff;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                font-size: 11px;
                line-height: 18px;
                text-align: center;
                cursor: pointer;
                display: none;
                z-index: 10;
                box-shadow: 0 2px 6px rgba(0,0,0,0.6);
            }
            .img-slot.has-img .btn-remove-img { display: block; }

            /* ปุ่มส่งรายงานยุทธวิธีหลัก (Tactical Action Trigger) */
            .btn-action {
                width: 100%;
                background: linear-gradient(180deg, #d4af37 0%, #8c6d15 100%);
                border: 1px solid var(--gold-accent);
                color: #000;
                padding: 14px;
                font-size: 16px;
                font-weight: 700;
                letter-spacing: 2px;
                cursor: pointer;
                border-radius: 12px;
                margin-top: 18px;
                text-transform: uppercase;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.6), 0 0 15px rgba(212, 175, 55, 0.2);
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }
            .btn-action:hover {
                background: linear-gradient(180deg, #f5d77f 0%, #a88424 100%);
                box-shadow: 0 0 25px var(--gold-glow);
                transform: translateY(-2px);
            }
            .btn-action:active {
                transform: translateY(0);
                box-shadow: inset 0 2px 6px rgba(0,0,0,0.7);
            }
            .btn-action:disabled {
                background: #202622;
                border-color: #3b453e;
                color: #616e66;
                cursor: not-allowed;
                box-shadow: none;
                transform: none;
            }
        </style>
    </head>
    <body>
        <div class="hud-container">
            <div class="thai-ribbon"></div>
            
            <div class="header-badge">
                <h1 class="title-main">PHANTOM SITREP</h1>
                <div class="title-sub">ROYAL THAI TACTICAL UNIT // RECON FEED</div>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>🔑 รหัสผ่าน (Passcode):</label>
                    <input type="password" id="passcode" placeholder="กรอกรหัสความปลอดภัย">
                </div>
                <div class="form-group">
                    <label>⚡ 1. สถานการณ์:</label>
                    <input type="text" id="situation" placeholder="เช่น การปะทะ / ตรวจพบ">
                </div>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>⏱️ 2. เวลาบันทึก:</label>
                    <input type="text" id="time_display" class="readonly-input" readonly>
                </div>
                <div class="form-group">
                    <label>🎖️ สัญลักษณ์ยุทธวิธี:</label>
                    <select id="tactical_icon" onchange="updatePinIconPreview()">
                        <option value="🎯 ตรวจพบเป้าหมาย">🎯 ตรวจพบเป้าหมาย (Target)</option>
                        <option value="⚔️ จุดปะทะ/ใช้อาวุธ">⚔️ จุดปะทะ (Contact)</option>
                        <option value="🛡️ ฐานปฏิบัติการ/ที่มั่น">🛡️ ฐานที่มั่น (FOB/Strongpoint)</option>
                        <option value="⚠️ วัตถุต้องสงสัย/IED">⚠️ วัตถุต้องสงสัย (Hazard/IED)</option>
                        <option value="🚁 จุดส่งกลับ/ลาน ฮ.">🚁 ลาน ฮ. / ส่งกลับ (LZ)</option>
                        <option value="⛺ จุดตรวจ/ค่ายพัก">⛺ จุดตรวจ (Checkpoint)</option>
                        <option value="💧 แหล่งน้ำ/เสบียง">💧 แหล่งเสบียง (Supply)</option>
                        <option value="📡 ที่ตั้งสื่อสาร/เรดาร์">📡 สถานีสื่อสาร (Comms/Radar)</option>
                    </select>
                </div>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>🌐 3.1 พิกัด GPS (LAT, LON):</label>
                    <input type="text" id="coords_display" placeholder="14.xxxxxx, 102.xxxxxx" onchange="manualCoordsInput(this.value)">
                </div>
                <div class="form-group">
                    <label>🎖️ 3.2 พิกัดทหาร (MGRS):</label>
                    <input type="text" id="mgrs_display" class="mgrs-input" readonly placeholder="คำนวณอัตโนมัติ...">
                </div>
            </div>

            <!-- กล่อง 3 ปุ่มเครื่องมือยุทธวิธีดีไซน์โมเดิร์น -->
            <div class="form-group" style="margin-top: -4px;">
                <div class="gps-tools">
                    <button type="button" class="tool-btn" onclick="getAutoGPS()">
                        <span style="font-size: 15px;">🛰️</span>
                        <span>AUTO GPS</span>
                    </button>
                    <button type="button" class="tool-btn primary-map" onclick="openMapModal()">
                        <span style="font-size: 15px;">🗺️</span>
                        <span>ปักหมุดแผนที่</span>
                    </button>
                    <button type="button" class="tool-btn radar-btn" onclick="window.open('/map', '_blank')">
                        <span style="font-size: 15px;">📡</span>
                        <span>เรดาร์รวม</span>
                    </button>
                </div>
                <div id="gps_status" class="status-tag">⚡ GPS: ค้นหาพิกัด...</div>
            </div>

            <div class="form-group">
                <label>📝 4. เหตุการณ์:</label>
                <textarea id="incident" rows="2" placeholder="ระบุรายละเอียดสิ่งที่ตรวจพบ / รูปแบบเหตุการณ์"></textarea>
            </div>

            <div class="form-group">
                <label>🛡️ 5. การปฏิบัติ:</label>
                <textarea id="action" rows="2" placeholder="ระบุการวางกำลัง / การใช้อาวุธ / การควบคุมพื้นที่"></textarea>
            </div>

            <div class="form-group">
                <label>📷 ภาพถ่ายพื้นที่ปฏิบัติการ (แตะเลือก/กด ✕ ลบ):</label>
                <input type="file" id="single_file_input" accept="image/*" style="display: none;" onchange="handleSingleFile(this.files)">
                <div class="img-grid">
                    <div class="img-slot" id="slot-0" onclick="triggerSlotUpload(0)"><span>+</span><div class="btn-remove-img" onclick="removeImage(event, 0)">✕</div></div>
                    <div class="img-slot" id="slot-1" onclick="triggerSlotUpload(1)"><span>+</span><div class="btn-remove-img" onclick="removeImage(event, 1)">✕</div></div>
                    <div class="img-slot" id="slot-2" onclick="triggerSlotUpload(2)"><span>+</span><div class="btn-remove-img" onclick="removeImage(event, 2)">✕</div></div>
                    <div class="img-slot" id="slot-3" onclick="triggerSlotUpload(3)"><span>+</span><div class="btn-remove-img" onclick="removeImage(event, 3)">✕</div></div>
                    <div class="img-slot" id="slot-4" onclick="triggerSlotUpload(4)"><span>+</span><div class="btn-remove-img" onclick="removeImage(event, 4)">✕</div></div>
                </div>
                <div id="img_count" class="status-tag">แนบภาพ: 0 / 5 ภาพ</div>
            </div>

            <button id="submit_btn" class="btn-action" onclick="submitReport()">ส่งรายงานยุทธวิธี</button>
        </div>

        <!-- หน้าต่าง Google Maps Mode เต็มจอพร้อมสลับ 4 ค่ายแผนที่ -->
        <div id="map-modal">
            <div class="map-app-container">
                <div id="tactical-map"></div>

                <!-- Center Fixed Marker with Tactical Icon -->
                <div class="center-pin-marker" id="center_pin">
                    <div class="pin-emoji-badge" id="marker_emoji_preview">🎯</div>
                    <div class="pin-shadow"></div>
                </div>

                <div class="map-top-bar">
                    <div class="map-top-row">
                        <div class="search-box-wrapper">
                            <span style="font-size:14px; margin-right:4px;">🔍</span>
                            <input type="text" id="map_search_input" placeholder="ค้นหาชื่อสถานที่ / อำเภอ / ค่าย..." onkeypress="if(event.key==='Enter') searchLocation()">
                        </div>
                        <div class="btn-circle-icon" onclick="closeMapModal()" style="color:#ff6b6b; font-size:18px;">✕</div>
                    </div>

                    <div class="provider-selector-bar">
                        <select id="map_provider_select" onchange="changeMapProvider(this.value)">
                            <option value="google_sat">🌐 Google Maps - ภาพถ่ายดาวเทียม (Hybrid)</option>
                            <option value="esri_sat">🛰️ ESRI World Imagery - ดาวเทียมยุทธวิธีทหาร</option>
                            <option value="google_road">🗺️ Google Maps - แผนที่ถนนมาตรฐาน</option>
                            <option value="osm_road">🧭 OpenStreetMap - แผนที่เส้นทางชุมชน</option>
                            <option value="opentopo">⛰️ OpenTopoMap - แผนที่ภูมิประเทศ/เส้นชั้นความสูง</option>
                        </select>
                    </div>
                </div>

                <div class="map-floating-controls">
                    <div class="btn-circle-icon" onclick="locateUserOnMap()" title="ล็อกตำแหน่ง GPS ตัวเอง">🎯</div>
                </div>

                <div class="map-bottom-sheet">
                    <div>
                        <div class="coord-info-title" id="sheet_symbol_title">🎯 ตรวจพบเป้าหมาย</div>
                        <div class="coord-info-val" id="sheet_coords">14.967565, 102.081882</div>
                        <div class="coord-mgrs-val" id="sheet_mgrs">MGRS: คำนวณ...</div>
                    </div>
                    <button type="button" class="btn-confirm-pin" onclick="confirmCenterPin()">ปักหมุดจุดนี้</button>
                </div>
            </div>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/mgrs@1.0.0/dist/mgrs.min.js"></script>
        <script>
            let userLat = 14.967565;
            let userLon = 102.081882;
            let currentPinLat = 14.967565;
            let currentPinLon = 102.081882;
            let currentMGRS = "";
            let imagesArray = [null, null, null, null, null];
            let activeSlotIndex = 0;
            let map, currentLayer;

            const mapLayers = {
                google_sat: L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
                    maxZoom: 20,
                    subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
                }),
                esri_sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                    maxZoom: 19
                }),
                google_road: L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
                    maxZoom: 20,
                    subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
                }),
                osm_road: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19
                }),
                opentopo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
                    maxZoom: 17
                })
            };

            function updateTime() {
                const now = new Date();
                document.getElementById('time_display').value = now.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' });
            }
            updateTime();

            function updatePinIconPreview() {
                const sel = document.getElementById('tactical_icon').value;
                const emoji = sel.split(' ')[0];
                document.getElementById('marker_emoji_preview').innerText = emoji;
                document.getElementById('sheet_symbol_title').innerText = sel;
            }

            function convertToMGRS(lat, lon) {
                try {
                    if (typeof mgrs !== 'undefined' && mgrs.forward) {
                        const raw = mgrs.forward([lon, lat], 5);
                        if (raw.length >= 15) {
                            return `${raw.slice(0, 3)} ${raw.slice(3, 5)} ${raw.slice(5, 10)} ${raw.slice(10, 15)}`;
                        }
                        return raw;
                    }
                } catch (e) {
                    console.error("MGRS error:", e);
                }
                return "N/A";
            }

            function getAutoGPS() {
                const status = document.getElementById('gps_status');
                status.innerText = "⚡ GPS: กำลังตรวจจับดาวเทียม...";
                status.style.color = "#d4af37";

                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            userLat = pos.coords.latitude;
                            userLon = pos.coords.longitude;
                            currentPinLat = userLat;
                            currentPinLon = userLon;
                            updateCoordsDisplay();
                            status.innerText = "⚡ GPS: ล็อกพิกัดดาวเทียมสำเร็จ";
                            status.style.color = "#7ee0ad";
                        },
                        (err) => {
                            status.innerText = "⚠️ GPS: ออฟไลน์ / กำหนดพิกัดเอง";
                            status.style.color = "#e57373";
                        },
                        { enableHighAccuracy: true, timeout: 10000 }
                    );
                } else {
                    status.innerText = "⚠️ GPS: ไม่รองรับบนอุปกรณ์นี้";
                }
            }
            getAutoGPS();

            function updateCoordsDisplay() {
                document.getElementById('coords_display').value = `${userLat.toFixed(6)}, ${userLon.toFixed(6)}`;
                currentMGRS = convertToMGRS(userLat, userLon);
                document.getElementById('mgrs_display').value = currentMGRS;
            }

            function manualCoordsInput(val) {
                const parts = val.split(',');
                if (parts.length === 2) {
                    const lat = parseFloat(parts[0].trim());
                    const lon = parseFloat(parts[1].trim());
                    if (!isNaN(lat) && !isNaN(lon)) {
                        userLat = lat;
                        userLon = lon;
                        currentPinLat = lat;
                        currentPinLon = lon;
                        updateCoordsDisplay();
                        document.getElementById('gps_status').innerText = "📍 พิกัด: กำหนดตำแหน่งเอง";
                        document.getElementById('gps_status').style.color = "#d4af37";
                    }
                }
            }

            function initInteractiveMap() {
                updatePinIconPreview();
                if (!map) {
                    map = L.map('tactical-map', {
                        zoomControl: false,
                        attributionControl: false
                    }).setView([currentPinLat, currentPinLon], 16);

                    currentLayer = mapLayers.google_sat;
                    currentLayer.addTo(map);

                    const pinElement = document.getElementById('center_pin');

                    map.on('movestart', () => {
                        pinElement.classList.add('dragging');
                    });

                    map.on('move', () => {
                        const center = map.getCenter();
                        currentPinLat = center.lat;
                        currentPinLon = center.lng;
                        document.getElementById('sheet_coords').innerText = `${currentPinLat.toFixed(6)}, ${currentPinLon.toFixed(6)}`;
                        const mgrsText = convertToMGRS(currentPinLat, currentPinLon);
                        document.getElementById('sheet_mgrs').innerText = `MGRS: ${mgrsText}`;
                    });

                    map.on('moveend', () => {
                        pinElement.classList.remove('dragging');
                    });
                } else {
                    map.setView([currentPinLat, currentPinLon], 16);
                }
                document.getElementById('sheet_coords').innerText = `${currentPinLat.toFixed(6)}, ${currentPinLon.toFixed(6)}`;
                document.getElementById('sheet_mgrs').innerText = `MGRS: ${convertToMGRS(currentPinLat, currentPinLon)}`;
            }

            function changeMapProvider(providerKey) {
                if (map && mapLayers[providerKey]) {
                    if (currentLayer) map.removeLayer(currentLayer);
                    currentLayer = mapLayers[providerKey];
                    currentLayer.addTo(map);
                }
            }

            function openMapModal() {
                const modal = document.getElementById('map-modal');
                modal.classList.add('show');
                setTimeout(() => {
                    initInteractiveMap();
                    map.invalidateSize();
                }, 150);
            }

            function closeMapModal() {
                document.getElementById('map-modal').classList.remove('show');
            }

            function locateUserOnMap() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition((pos) => {
                        map.flyTo([pos.coords.latitude, pos.coords.longitude], 17, {
                            animate: true,
                            duration: 1.2
                        });
                    }, null, { enableHighAccuracy: true });
                }
            }

            async function searchLocation() {
                const query = document.getElementById('map_search_input').value.trim();
                if (!query) return;
                try {
                    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&countrycodes=th`);
                    const data = await res.json();
                    if (data && data.length > 0) {
                        const lat = parseFloat(data[0].lat);
                        const lon = parseFloat(data[0].lon);
                        map.flyTo([lat, lon], 16, { animate: true, duration: 1.5 });
                    } else {
                        alert('ไม่พบสถานที่ดังกล่าว กรุณาลองค้นหาด้วยชื่ออื่น');
                    }
                } catch (err) {
                    console.log("Search error", err);
                }
            }

            function confirmCenterPin() {
                userLat = currentPinLat;
                userLon = currentPinLon;
                updateCoordsDisplay();
                document.getElementById('gps_status').innerText = "🎯 พิกัด: ปักหมุดแม่นยำ (MGRS)";
                document.getElementById('gps_status').style.color = "#00ffcc";
                closeMapModal();
            }

            function triggerSlotUpload(index) {
                activeSlotIndex = index;
                document.getElementById('single_file_input').click();
            }

            function handleSingleFile(files) {
                if (files && files[0]) {
                    const file = files[0];
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        imagesArray[activeSlotIndex] = e.target.result;
                        renderSlot(activeSlotIndex);
                        updateImageCount();
                    };
                    reader.readAsDataURL(file);
                }
                document.getElementById('single_file_input').value = "";
            }

            function removeImage(event, index) {
                event.stopPropagation();
                imagesArray[index] = null;
                renderSlot(index);
                updateImageCount();
            }

            function renderSlot(index) {
                const slot = document.getElementById(`slot-${index}`);
                if (imagesArray[index]) {
                    slot.classList.add('has-img');
                    slot.innerHTML = `
                        <img src="${imagesArray[index]}">
                        <div class="btn-remove-img" onclick="removeImage(event, ${index})">✕</div>
                    `;
                } else {
                    slot.classList.remove('has-img');
                    slot.innerHTML = `
                        <span>+</span>
                        <div class="btn-remove-img" onclick="removeImage(event, ${index})">✕</div>
                    `;
                }
            }

            function updateImageCount() {
                const count = imagesArray.filter(img => img !== null).length;
                document.getElementById('img_count').innerText = `แนบภาพ: ${count} / 5 ภาพ`;
            }

            async function submitReport() {
                const passcode = document.getElementById('passcode').value;
                const situation = document.getElementById('situation').value;
                const incident = document.getElementById('incident').value;
                const action = document.getElementById('action').value;
                const tacticalIcon = document.getElementById('tactical_icon').value;

                if (!passcode) { alert('กรุณากรอกรหัสผ่านความปลอดภัย'); return; }

                const validImages = imagesArray.filter(img => img !== null);

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
                            mgrs: currentMGRS,
                            tactical_icon: tacticalIcon,
                            images: validImages
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

# --- หน้าศูนย์รวมแผนที่ยุทธวิธี (TACTICAL MAP DASHBOARD พร้อมระบบล็อกรหัสผ่าน) ---
@app.get("/map", response_class=HTMLResponse)
def get_map_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PHANTOM - TACTICAL COMMON OPERATING PICTURE</title>
        <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            :root {
                --gold-accent: #d4af37;
                --gold-glow: rgba(212, 175, 55, 0.45);
                --thai-red: #d32f2f;
                --mgrs-green: #00ffcc;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body, html { width: 100%; height: 100%; overflow: hidden; font-family: 'Chakra Petch', sans-serif; background: #050806; }
            #dashboard-map { width: 100%; height: 100%; }

            #auth-gate {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.95)), url('/bg_new.jpg') center/cover;
                z-index: 99999;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .gate-box {
                width: 100%;
                max-width: 400px;
                background: rgba(10, 16, 13, 0.95);
                border: 1.5px solid var(--gold-accent);
                border-radius: 16px;
                padding: 32px 24px;
                box-shadow: 0 0 40px rgba(212, 175, 55, 0.25);
                text-align: center;
                backdrop-filter: blur(16px);
            }
            .gate-title {
                color: var(--gold-accent);
                font-size: 20px;
                font-weight: 700;
                letter-spacing: 2px;
                margin-bottom: 6px;
            }
            .gate-subtitle {
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                color: #8da196;
                margin-bottom: 22px;
                letter-spacing: 1px;
            }
            .gate-input {
                width: 100%;
                background: rgba(5, 8, 6, 0.85);
                border: 1px solid rgba(212, 175, 55, 0.4);
                border-radius: 10px;
                color: #fff;
                padding: 12px;
                font-size: 16px;
                text-align: center;
                font-family: 'Chakra Petch', sans-serif;
                margin-bottom: 16px;
                outline: none;
            }
            .gate-input:focus {
                border-color: var(--gold-accent);
                box-shadow: 0 0 15px var(--gold-glow);
            }
            .gate-btn {
                width: 100%;
                background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%);
                border: 1px solid var(--gold-accent);
                color: #000;
                font-weight: 700;
                font-size: 14px;
                padding: 13px;
                border-radius: 10px;
                cursor: pointer;
                text-transform: uppercase;
                letter-spacing: 1.5px;
                box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
                transition: 0.2s;
            }
            .gate-btn:active { transform: scale(0.98); }
            
            .header-bar {
                position: absolute;
                top: 15px;
                left: 15px;
                z-index: 1000;
                background: rgba(10, 16, 13, 0.94);
                border: 1.5px solid #d4af37;
                border-radius: 14px;
                padding: 10px 18px;
                backdrop-filter: blur(12px);
                box-shadow: 0 6px 25px rgba(0,0,0,0.8);
            }
            .header-bar h2 { font-size: 16px; color: #d4af37; letter-spacing: 2px; text-transform: uppercase; margin: 0; }
            .header-bar p { font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #00ffcc; margin: 2px 0 0 0; }

            .map-switch-top {
                position: absolute;
                top: 15px;
                right: 15px;
                z-index: 1000;
                background: rgba(10, 16, 13, 0.94);
                border: 1.5px solid #d4af37;
                border-radius: 12px;
                padding: 6px 14px;
                backdrop-filter: blur(12px);
            }
            .map-switch-top select {
                background: transparent;
                border: none;
                color: #d4af37;
                font-family: 'Chakra Petch', sans-serif;
                font-size: 13px;
                font-weight: 700;
                cursor: pointer;
                outline: none;
            }

            .leaflet-popup-content-wrapper {
                background: rgba(10, 16, 13, 0.96) !important;
                border: 1.5px solid #d4af37 !important;
                border-radius: 12px !important;
                color: #fff !important;
                font-family: 'Chakra Petch', sans-serif !important;
                backdrop-filter: blur(12px);
            }
            .leaflet-popup-tip { background: #d4af37 !important; }
            .popup-img { width: 100%; border-radius: 8px; margin-top: 8px; border: 1px solid rgba(212,175,55,0.4); }
            
            .custom-tactical-pin {
                font-size: 28px;
                text-align: center;
                filter: drop-shadow(0 4px 8px rgba(0,0,0,0.85));
                cursor: pointer;
            }
        </style>
    </head>
    <body>
        <div id="auth-gate">
            <div class="gate-box">
                <div style="font-size: 40px; margin-bottom: 8px;">🔒</div>
                <div class="gate-title">RESTRICTED ACCESS</div>
                <div class="gate-subtitle">TACTICAL RADAR OPERATIONS // AUTH REQUIRED</div>
                <input type="password" id="admin_key_input" class="gate-input" placeholder="กรอกรหัสผ่านผู้ดูแลระบบ" onkeypress="if(event.key==='Enter') verifyAdminKey()">
                <button type="button" class="gate-btn" onclick="verifyAdminKey()">เข้าสู่ศูนย์แผนที่ยุทธวิธี</button>
            </div>
        </div>

        <div class="header-bar">
            <h2>🗺️ PHANTOM TACTICAL RADAR MAP</h2>
            <p id="total_reports">กำลังโหลดพิกัดรายงานยุทธวิธี...</p>
        </div>

        <div class="map-switch-top">
            <select onchange="changeDashboardLayer(this.value)">
                <option value="google_sat">🌐 Google Maps (Satellite)</option>
                <option value="esri_sat">🛰️ ESRI World Imagery (Mil)</option>
                <option value="google_road">🗺️ Google Maps (Road)</option>
                <option value="opentopo">⛰️ OpenTopoMap (Terrain)</option>
            </select>
        </div>

        <div id="dashboard-map"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            const layers = {
                google_sat: L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                esri_sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 }),
                google_road: L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                opentopo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17 })
            };

            const map = L.map('dashboard-map', { attributionControl: false }).setView([14.967565, 102.081882], 12);
            let activeLayer = layers.google_sat;
            activeLayer.addTo(map);

            function changeDashboardLayer(k) {
                if (layers[k]) {
                    map.removeLayer(activeLayer);
                    activeLayer = layers[k];
                    activeLayer.addTo(map);
                }
            }

            async function verifyAdminKey() {
                const key = document.getElementById('admin_key_input').value.trim();
                if (!key) { alert('กรุณากรอกรหัสผ่านเพื่อเข้าใช้งาน'); return; }

                try {
                    const res = await fetch(`/api/get-all-reports?passcode=${encodeURIComponent(key)}`);
                    if (res.status === 403 || res.status === 401) {
                        alert('❌ รหัสผ่านความปลอดภัยไม่ถูกต้อง! ปฏิเสธการเข้าถึง');
                        return;
                    }
                    const data = await res.json();
                    
                    document.getElementById('auth-gate').style.display = 'none';
                    map.invalidateSize();
                    
                    renderMapData(data);
                } catch (e) {
                    alert('⚠️ เกิดข้อผิดพลาดในการตรวจสอบสิทธิ์การเข้าถึง');
                }
            }

            function renderMapData(data) {
                if (data && data.length > 0) {
                    document.getElementById('total_reports').innerText = `ตรวจพบรายงานทั้งหมด: ${data.length} จุดยุทธวิธี`;
                    const group = [];

                    data.forEach(item => {
                        if (item.latitude && item.longitude) {
                            const detail = item.detail || "";
                            let emoji = "🎯";
                            const match = detail.match(/🎖️ สัญลักษณ์ยุทธวิธี: (\\S+)/);
                            if (match) emoji = match[1];

                            const customIcon = L.divIcon({
                                className: 'custom-tactical-pin',
                                html: emoji,
                                iconSize: [30, 30],
                                iconAnchor: [15, 15]
                            });

                            const marker = L.marker([item.latitude, item.longitude], { icon: customIcon }).addTo(map);
                            
                            let imgHtml = "";
                            if (item.image_url) {
                                imgHtml = `<a href="${item.image_url}" target="_blank"><img src="${item.image_url}" class="popup-img"></a>`;
                            }

                            marker.bindPopup(`
                                <div style="min-width: 220px;">
                                    <div style="font-size:15px; font-weight:bold; color:#d4af37; margin-bottom:4px;">${emoji} รายงานสถานการณ์</div>
                                    <div style="font-size:12px; white-space: pre-line; color:#cfd8dc; line-height:1.4;">${detail}</div>
                                    ${imgHtml}
                                </div>
                            `);
                            group.push([item.latitude, item.longitude]);
                        }
                    });

                    if (group.length > 0) {
                        map.fitBounds(group, { padding: [50, 50] });
                    }
                } else {
                    document.getElementById('total_reports').innerText = "ยังไม่มีรายงานในระบบ";
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/get-all-reports")
def get_all_reports(passcode: str = ""):
    if passcode != ADMIN_MAP_PASSCODE:
        raise HTTPException(status_code=403, detail="สิทธิ์การเข้าถึงไม่ถูกต้อง กรุณากรอกรหัสผ่านความปลอดภัย")

    try:
        response = supabase.table("reports").select("*").order("created_at", desc=True).limit(100).execute()
        return response.data
    except Exception as e:
        print(f"Fetch all error: {e}")
        return []

@app.post("/api/submit-report")
async def submit_report(payload: ReportPayload):
    if payload.passcode != REPORT_PASSCODE:
        raise HTTPException(status_code=400, detail="รหัสผ่านความปลอดภัยไม่ถูกต้อง!")

    now = datetime.now(THAILAND_TZ)
    time_str = now.strftime("%d/%m/%Y %H:%M:%S")

    uploaded_image_urls = []
    
    if payload.images:
        for idx, img_b64 in enumerate(payload.images):
            try:
                if "," in img_b64:
                    header, base64_data = img_b64.split(",", 1)
                else:
                    base64_data = img_b64
                
                file_bytes = base64.b64decode(base64_data)
                filename = f"tactical_{int(now.timestamp())}_{uuid.uuid4().hex[:6]}_{idx}.jpg"
                
                supabase.storage.from_("reports").upload(
                    path=filename,
                    file=file_bytes,
                    file_options={"content-type": "image/jpeg"}
                )
                
                public_url = supabase.storage.from_("reports").get_public_url(filename)
                uploaded_image_urls.append(public_url)
            except Exception as upload_err:
                print(f"Image upload error for item {idx}: {upload_err}")

    first_image_url = uploaded_image_urls[0] if uploaded_image_urls else None
    mgrs_str = payload.mgrs if payload.mgrs else "N/A"

    try:
        report_data = {
            "user_id": payload.user_id,
            "report_type": "รายงานยุทธวิธี (PHANTOM HUD)",
            "detail": (
                f"เวลา: {time_str}\n"
                f"🎖️ สัญลักษณ์ยุทธวิธี: {payload.tactical_icon}\n"
                f"1. สถานการณ์: {payload.situation}\n"
                f"3. เหตุการณ์: {payload.incident}\n"
                f"5. การปฏิบัติ: {payload.action}\n"
                f"🎖️ พิกัดทหาร (MGRS): {mgrs_str}\n"
                f"🌐 พิกัด GPS: {payload.latitude:.6f}, {payload.longitude:.6f}\n"
                f"📍 แผนที่: https://maps.google.com/?q={payload.latitude},{payload.longitude}\n"
                f"จำนวนภาพถ่าย: {len(uploaded_image_urls)} ภาพ"
            ),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "image_url": first_image_url
        }
        supabase.table("reports").insert(report_data).execute()
    except Exception as err:
        print(f"Supabase error: {err}")
        raise HTTPException(status_code=500, detail="ไม่สามารถบันทึกข้อมูลลงฐานข้อมูลได้")

    return {"status": "success", "time": time_str, "images_count": len(uploaded_image_urls)}

@app.post("/callback")
async def callback(request: Request):
    return Response(content="OK", status_code=200)
