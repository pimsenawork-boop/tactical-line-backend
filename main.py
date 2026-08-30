import os
import re
import uuid
import base64
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# LINE Bot SDK v3
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    JoinEvent
)
from supabase import create_client, Client

app = FastAPI()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

TARGET_GROUP_ID = os.getenv("LINE_TARGET_GROUP_ID", "")

REPORT_PASSCODE = "phantom2"
ADMIN_PASSCODE = "phantomadmin"
EDIT_PASSCODE = "wisarut"

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
    radius_meters: Optional[int] = 0
    mgrs: Optional[str] = ""
    tactical_icon: Optional[str] = "🎯 ตรวจพบเป้าหมาย"
    images: Optional[List[str]] = []
    user_id: str = "PHANTOM_OPERATOR"

class UpdateReportPayload(BaseModel):
    passcode: str
    report_id: int
    situation: str
    incident: str
    action: str

class DeleteReportPayload(BaseModel):
    passcode: str
    report_id: int

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

# --- หน้าฟอร์มส่งรายงาน SITREP ---
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
                --gold-glow: rgba(212, 175, 55, 0.45);
                --border-subtle: rgba(212, 175, 55, 0.35);
                --thai-red: #a51c24;
                --thai-blue: #1c2c59;
                --mgrs-green: #00ffcc;
            }
            * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
            
            body {
                margin: 0;
                padding: 16px 12px;
                font-family: 'Chakra Petch', sans-serif;
                background-color: #060907;
                background-image: 
                    linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.7)),
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
                max-width: 520px;
                background-image: 
                    linear-gradient(rgba(10, 15, 12, 0.85), rgba(6, 10, 8, 0.92)),
                    url('/bg.jpg');
                background-size: cover;
                background-position: center center;
                border: 1.5px solid var(--border-subtle);
                border-radius: 16px;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9), 0 0 25px rgba(212, 175, 55, 0.15);
                padding: 24px 20px;
                position: relative;
                overflow: hidden;
            }

            .thai-ribbon {
                position: absolute;
                top: 0; right: 0;
                width: 90px; height: 4px;
                background: linear-gradient(90deg, var(--thai-red) 0% 20%, #fff 20% 40%, var(--thai-blue) 40% 60%, #fff 60% 80%, var(--thai-red) 80% 100%);
            }

            .header-badge { text-align: center; margin-bottom: 18px; position: relative; }
            .title-main {
                font-size: 21px; font-weight: 700; color: var(--gold-accent);
                letter-spacing: 2.5px; text-transform: uppercase; margin: 0;
                text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9);
            }
            .title-sub {
                font-family: 'Share Tech Mono', monospace; font-size: 11px;
                color: #8da196; letter-spacing: 1.2px; margin-top: 3px;
            }

            .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .form-group { margin-bottom: 12px; }
            label {
                display: block; font-size: 12.5px; font-weight: 600;
                color: #a2b5aa; margin-bottom: 5px; letter-spacing: 0.5px;
            }

            input, textarea, select {
                width: 100%;
                background-image: linear-gradient(rgba(5, 8, 6, 0.8), rgba(5, 8, 6, 0.9)), url('/bg.jpg');
                background-size: cover; background-position: center;
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px; color: #ffffff; padding: 10px 12px;
                font-family: 'Chakra Petch', sans-serif; font-size: 14px; transition: all 0.25s ease;
            }
            input:focus, textarea:focus, select:focus {
                outline: none; border-color: var(--gold-accent);
                background-image: linear-gradient(rgba(12, 18, 14, 0.75), rgba(12, 18, 14, 0.9)), url('/bg.jpg');
                box-shadow: 0 0 12px var(--gold-glow);
            }
            .readonly-input {
                font-family: 'Share Tech Mono', monospace; color: #7ee0ad;
                background-image: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.85)), url('/bg.jpg');
                border-color: rgba(255, 255, 255, 0.08);
            }
            .mgrs-input {
                font-family: 'Share Tech Mono', monospace; color: var(--mgrs-green) !important;
                font-weight: 700; letter-spacing: 1.2px;
                background-image: linear-gradient(rgba(0, 20, 15, 0.75), rgba(0, 15, 10, 0.9)), url('/bg.jpg');
                border-color: rgba(0, 255, 204, 0.35);
            }
            textarea { resize: vertical; min-height: 55px; }

            .gps-tools { display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 8px; margin-top: 6px; }
            .tool-btn {
                background: linear-gradient(180deg, rgba(30, 42, 35, 0.9) 0%, rgba(15, 22, 18, 0.9) 100%);
                border: 1px solid rgba(212, 175, 55, 0.35); color: var(--gold-accent);
                padding: 9px 6px; font-size: 12px; font-weight: 600; border-radius: 8px;
                cursor: pointer; transition: 0.2s; text-align: center;
                display: flex; align-items: center; justify-content: center; gap: 4px;
            }
            .tool-btn:hover { border-color: var(--gold-accent); box-shadow: 0 0 10px var(--gold-glow); color: #fff; }
            .tool-btn:active { transform: scale(0.96); }
            .tool-btn.highlight {
                border-color: var(--gold-accent);
                background: linear-gradient(180deg, rgba(212, 175, 55, 0.25) 0%, rgba(160, 130, 30, 0.2) 100%);
            }

            /* --- MAP MODAL --- */
            #map-modal {
                display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px); z-index: 10000;
                opacity: 0; transition: opacity 0.25s ease;
            }
            #map-modal.show { display: flex; opacity: 1; }
            .map-app-container { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
            #tactical-map { position: absolute; top: 0; left: 0; right: 0; bottom: 0; width: 100%; height: 100%; z-index: 1; }

            .map-top-bar {
                position: absolute; top: 15px; left: 15px; right: 15px; z-index: 1000;
                display: flex; flex-direction: column; gap: 8px;
            }
            .map-top-row { display: flex; gap: 8px; }
            .search-box-wrapper {
                flex: 1; background: rgba(18, 24, 20, 0.94); backdrop-filter: blur(12px);
                border: 1px solid rgba(212, 175, 55, 0.4); border-radius: 25px;
                display: flex; align-items: center; padding: 4px 14px;
            }
            .search-box-wrapper input { background: transparent; border: none; padding: 6px 8px; font-size: 14px; color: #fff; }
            .search-box-wrapper input:focus { background: transparent; border: none; }
            .btn-circle-icon {
                width: 44px; height: 44px; border-radius: 50%; background: rgba(18, 24, 20, 0.94);
                border: 1px solid rgba(212, 175, 55, 0.4); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 16px; cursor: pointer;
            }

            .provider-selector-bar {
                background: rgba(18, 24, 20, 0.94); border: 1px solid rgba(212, 175, 55, 0.4);
                border-radius: 10px; padding: 4px 10px;
            }
            .provider-selector-bar select { background: transparent; border: none; color: var(--gold-accent); font-size: 12.5px; font-weight: 600; }

            .map-floating-controls { position: absolute; right: 15px; bottom: 180px; z-index: 1000; }
            .center-pin-marker {
                position: absolute; top: 50%; left: 50%; transform: translate(-50%, -100%);
                z-index: 100; pointer-events: none; text-align: center;
            }
            .center-pin-marker.dragging { transform: translate(-50%, -120%) scale(1.1); }
            .pin-emoji-badge { font-size: 24px; filter: drop-shadow(0 3px 6px rgba(0,0,0,0.8)); }
            .pin-shadow {
                position: absolute; bottom: -2px; left: 50%; transform: translateX(-50%);
                width: 12px; height: 4px; background: rgba(0,0,0,0.6); border-radius: 50%; filter: blur(1px);
            }

            .map-bottom-sheet {
                position: absolute; bottom: 15px; left: 15px; right: 15px; z-index: 1000;
                background: rgba(12, 18, 14, 0.95); backdrop-filter: blur(16px);
                border: 1.5px solid var(--border-subtle); border-radius: 16px;
                padding: 14px 16px; display: flex; flex-direction: column; gap: 10px;
            }
            .sheet-row-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
            .radius-control-bar {
                display: flex; align-items: center; gap: 8px;
                border-top: 1px solid rgba(212, 175, 55, 0.2); padding-top: 8px;
            }
            .radius-control-bar label { font-size: 11.5px; color: #ff6b6b; font-weight: 700; margin: 0; white-space: nowrap; }
            .radius-control-bar select {
                background: rgba(0,0,0,0.6); border: 1px solid rgba(255, 107, 107, 0.4);
                color: #ff6b6b; padding: 5px 8px; font-size: 12px; font-weight: bold; border-radius: 6px; flex: 1;
            }

            .coord-info-title { font-size: 11px; color: #8da196; text-transform: uppercase; letter-spacing: 1px; }
            .coord-info-val { font-family: 'Share Tech Mono', monospace; font-size: 13.5px; font-weight: 700; color: #7ee0ad; margin-top: 2px; }
            .coord-mgrs-val { font-family: 'Share Tech Mono', monospace; font-size: 13.5px; font-weight: 700; color: var(--mgrs-green); margin-top: 1px; }
            .btn-confirm-pin {
                background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%);
                border: 1px solid var(--gold-accent); color: #000; font-weight: 700;
                font-size: 13px; padding: 10px 18px; border-radius: 10px; cursor: pointer; text-transform: uppercase;
            }

            .img-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 6px; }
            .img-slot {
                aspect-ratio: 1 / 1;
                background-image: linear-gradient(rgba(5, 8, 6, 0.65), rgba(5, 8, 6, 0.75)), url('/bg.jpg');
                background-size: cover; background-position: center;
                border: 1px dashed rgba(212, 175, 55, 0.4);
                border-radius: 7px; display: flex; align-items: center; justify-content: center; cursor: pointer; overflow: hidden; position: relative;
            }
            .img-slot:hover { border-color: var(--gold-accent); box-shadow: 0 0 10px var(--gold-glow); }
            .img-slot img { width: 100%; height: 100%; object-fit: cover; }
            .img-slot span { font-size: 20px; color: var(--gold-accent); }
            .btn-remove-img {
                position: absolute; top: 2px; right: 2px; background: rgba(165, 28, 36, 0.88);
                color: #fff; border: 1px solid #fff; border-radius: 50%; width: 18px; height: 18px; font-size: 11px; line-height: 16px; text-align: center; cursor: pointer; display: none; z-index: 10;
            }
            .img-slot.has-img .btn-remove-img { display: block; }

            .btn-action {
                width: 100%; background: linear-gradient(180deg, #d4af37 0%, #7d6017 100%);
                border: 1px solid var(--gold-accent); color: #000; padding: 13px;
                font-size: 15px; font-weight: 700; letter-spacing: 2px; cursor: pointer;
                border-radius: 10px; margin-top: 15px; text-transform: uppercase; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); transition: all 0.25s ease;
            }
            .btn-action:hover { background: linear-gradient(180deg, #f5d77f 0%, #a88424 100%); box-shadow: 0 0 15px var(--gold-glow); transform: translateY(-1px); }
            .btn-action:disabled { background: #252826; border-color: #3b403d; color: #6a736e; cursor: not-allowed; box-shadow: none; transform: none; }
            .status-tag { font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #8da196; margin-top: 4px; }
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
                    <input type="password" id="passcode" placeholder="กรอกรหัสส่งรายงาน">
                </div>
                <div class="form-group">
                    <label>สถานการณ์:</label>
                    <input type="text" id="situation" placeholder="เช่น การปะทะ / ตรวจพบ">
                </div>
            </div>

            <div class="grid-2">
                <div class="form-group">
                    <label>เวลาบันทึก (AUTO):</label>
                    <input type="text" id="time_display" class="readonly-input" readonly>
                </div>
                <div class="form-group">
                    <label>สัญลักษณ์ยุทธวิธี:</label>
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
                    <label>พิกัด GPS (LAT, LON):</label>
                    <input type="text" id="coords_display" placeholder="14.xxxxxx, 102.xxxxxx" onchange="manualCoordsInput(this.value)">
                </div>
                <div class="form-group">
                    <label>พิกัดทหาร (MGRS):</label>
                    <input type="text" id="mgrs_display" class="mgrs-input" readonly placeholder="คำนวณอัตโนมัติ...">
                </div>
            </div>

            <div class="form-group">
                <label>รัศมีอันตราย / รัศมีปฏิบัติการ:</label>
                <select id="danger_radius">
                    <option value="0">0 ม. (ไม่ระบุรัศมี / จุดเฉพาะ)</option>
                    <option value="50">50 เมตร (รัศมีประชิด / ระเบิดขว้าง)</option>
                    <option value="100">100 เมตร (รัศมีอาวุธยิงสนับสนุน)</option>
                    <option value="250">250 เมตร (รัศมีลูกปืน ค. / IED ขนาดกลาง)</option>
                    <option value="500">500 เมตร (รัศมีควบคุมพื้นที่ / ปิดล้อม)</option>
                    <option value="1000">1,000 เมตร (1 กม. - รัศมีลาดตระเวน)</option>
                    <option value="2000">2,000 เมตร (2 กม. - รัศมีปืนใหญ่/ตรวจการณ์)</option>
                    <option value="5000">5,000 เมตร (5 กม. - ขอบเขตยุทธวิธีระดับกองพัน)</option>
                    <option value="10000">10,000 เมตร (10 กม. - ขอบเขตยุทธศาสตร์สูงสุด)</option>
                </select>
            </div>

            <div class="form-group" style="margin-top: -4px;">
                <div class="gps-tools">
                    <button type="button" class="tool-btn" onclick="getAutoGPS()">🛰️ AUTO GPS</button>
                    <button type="button" class="tool-btn highlight" onclick="openMapModal()">🗺️ ปักหมุดแผนที่</button>
                    <button type="button" class="tool-btn" onclick="window.open('/map', '_blank')">🌐 แผนที่รวม</button>
                </div>
                <div id="gps_status" class="status-tag">⚡ GPS: ค้นหาพิกัด...</div>
            </div>

            <div class="form-group">
                <label>เหตุการณ์:</label>
                <textarea id="incident" rows="2" placeholder="ระบุรายละเอียดสิ่งที่ตรวจพบ / รูปแบบเหตุการณ์"></textarea>
            </div>

            <div class="form-group">
                <label>การปฏิบัติ:</label>
                <textarea id="action" rows="2" placeholder="ระบุการวางกำลัง / การใช้อาวุธ / การควบคุมพื้นที่"></textarea>
            </div>

            <div class="form-group">
                <label>📷 ภาพถ่ายพื้นที่ปฏิบัติการ (แตะเพื่อเปลี่ยน/กด ✕ เพื่อลบ):</label>
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

        <div id="map-modal">
            <div class="map-app-container">
                <div id="tactical-map"></div>

                <div class="center-pin-marker" id="center_pin">
                    <div class="pin-emoji-badge" id="marker_emoji_preview">🎯</div>
                    <div class="pin-shadow"></div>
                </div>

                <div class="map-top-bar">
                    <div class="map-top-row">
                        <div class="search-box-wrapper">
                            <span style="font-size:14px; margin-right:4px;">🔍</span>
                            <input type="text" id="map_search_input" placeholder="ค้นหา: พิกัด Lat,Lon / MGRS / ชื่อสถานที่..." onkeypress="if(event.key==='Enter') searchLocation()">
                            <button type="button" onclick="searchLocation()" style="background:transparent; border:none; color:var(--gold-accent); cursor:pointer; font-weight:bold; font-size:12px; margin-left:4px;">ค้นหา</button>
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
                    <div class="sheet-row-top">
                        <div>
                            <div class="coord-info-title" id="sheet_symbol_title">🎯 ตรวจพบเป้าหมาย</div>
                            <div class="coord-info-val" id="sheet_coords">14.967565, 102.081882</div>
                            <div class="coord-mgrs-val" id="sheet_mgrs">MGRS: คำนวณ...</div>
                        </div>
                        <button type="button" class="btn-confirm-pin" onclick="confirmCenterPin()">ปักหมุดจุดนี้</button>
                    </div>

                    <div class="radius-control-bar">
                        <label>⭕ รัศมีอันตราย:</label>
                        <select id="modal_radius_select" onchange="updateModalRadiusCircle(this.value)">
                            <option value="0">0 ม. (ไม่ระบุ)</option>
                            <option value="50">50 เมตร</option>
                            <option value="100">100 เมตร</option>
                            <option value="250">250 เมตร</option>
                            <option value="500">500 เมตร</option>
                            <option value="1000">1,000 เมตร (1 กม.)</option>
                            <option value="2000">2,000 เมตร (2 กม.)</option>
                            <option value="5000">5,000 เมตร (5 กม.)</option>
                            <option value="10000">10,000 เมตร (10 กม.)</option>
                        </select>
                    </div>
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
            let map, currentLayer, radiusCircle;

            const mapLayers = {
                google_sat: L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                esri_sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 }),
                google_road: L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                osm_road: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }),
                opentopo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17 })
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
                            status.innerText = "⚡ GPS: พิกัดล็อกตำแหน่งแล้ว";
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

            function updateModalRadiusCircle(radiusVal) {
                const r = parseInt(radiusVal);
                if (radiusCircle) { map.removeLayer(radiusCircle); radiusCircle = null; }
                if (r > 0 && map) {
                    radiusCircle = L.circle([currentPinLat, currentPinLon], {
                        radius: r, color: '#ff3b30', fillColor: '#ff3b30',
                        fillOpacity: 0.22, weight: 2, dashArray: '4, 6'
                    }).addTo(map);
                }
                document.getElementById('danger_radius').value = radiusVal;
            }

            function initInteractiveMap() {
                updatePinIconPreview();
                const selRadius = document.getElementById('danger_radius').value;
                document.getElementById('modal_radius_select').value = selRadius;

                if (!map) {
                    map = L.map('tactical-map', {
                        zoomControl: false, attributionControl: false
                    }).setView([currentPinLat, currentPinLon], 16);

                    currentLayer = mapLayers.google_sat;
                    currentLayer.addTo(map);

                    const pinElement = document.getElementById('center_pin');

                    map.on('movestart', () => { pinElement.classList.add('dragging'); });
                    map.on('move', () => {
                        const center = map.getCenter();
                        currentPinLat = center.lat;
                        currentPinLon = center.lng;
                        document.getElementById('sheet_coords').innerText = `${currentPinLat.toFixed(6)}, ${currentPinLon.toFixed(6)}`;
                        const mgrsText = convertToMGRS(currentPinLat, currentPinLon);
                        document.getElementById('sheet_mgrs').innerText = `MGRS: ${mgrsText}`;
                        if (radiusCircle) { radiusCircle.setLatLng(center); }
                    });
                    map.on('moveend', () => { pinElement.classList.remove('dragging'); });
                } else {
                    map.setView([currentPinLat, currentPinLon], 16);
                }

                updateModalRadiusCircle(selRadius);
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
                        map.flyTo([pos.coords.latitude, pos.coords.longitude], 17, { animate: true, duration: 1.2 });
                    }, null, { enableHighAccuracy: true });
                }
            }

            // ฟังก์ชันค้นหาอัจฉริยะ (Smart Location & Coordinate Parser)
            async function searchLocation() {
                const query = document.getElementById('map_search_input').value.trim();
                if (!query) return;

                // 1. ตรวจสอบรูปแบบพิกัด GPS (Lat, Lon)
                const latLonRegex = /^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)[,\s]+[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$/;
                if (latLonRegex.test(query)) {
                    const parts = query.split(/[\s,]+/);
                    const lat = parseFloat(parts[0]);
                    const lon = parseFloat(parts[1]);
                    if (!isNaN(lat) && !isNaN(lon)) {
                        map.flyTo([lat, lon], 17, { animate: true, duration: 1.2 });
                        return;
                    }
                }

                // 2. ตรวจสอบรูปแบบพิกัดทหาร MGRS
                try {
                    const cleanMGRS = query.replace(/\s+/g, '').toUpperCase();
                    if (typeof mgrs !== 'undefined' && mgrs.toPoint) {
                        const point = mgrs.toPoint(cleanMGRS);
                        if (point && point.length === 2) {
                            const lon = point[0];
                            const lat = point[1];
                            map.flyTo([lat, lon], 17, { animate: true, duration: 1.2 });
                            return;
                        }
                    }
                } catch (e) {
                    // หากไม่ใช่ MGRS ให้ข้ามไปค้นหาชื่อสถานที่ต่อไป
                }

                // 3. ค้นหาด้วยชื่อสถานที่ / ค่าย / อำเภอ ผ่าน Nominatim API
                try {
                    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&countrycodes=th`);
                    const data = await res.json();
                    if (data && data.length > 0) {
                        const lat = parseFloat(data[0].lat);
                        const lon = parseFloat(data[0].lon);
                        map.flyTo([lat, lon], 16, { animate: true, duration: 1.5 });
                    } else {
                        alert('⚠️ ไม่พบข้อมูลพิกัดหรือสถานที่ดังกล่าว กรุณาตรวจสอบความถูกต้อง');
                    }
                } catch (err) {
                    alert('⚠️ ไม่สามารถค้นหาสถานที่ได้ กรุณาตรวจสอบการเชื่อมต่อ');
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
                    slot.innerHTML = `<img src="${imagesArray[index]}"><div class="btn-remove-img" onclick="removeImage(event, ${index})">✕</div>`;
                } else {
                    slot.classList.remove('has-img');
                    slot.innerHTML = `<span>+</span><div class="btn-remove-img" onclick="removeImage(event, ${index})">✕</div>`;
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
                const radiusMeters = parseInt(document.getElementById('danger_radius').value) || 0;

                if (!passcode) { alert('กรุณากรอกรหัสผ่านความปลอดภัย'); return; }

                const validImages = imagesArray.filter(img => img !== null);
                const btn = document.getElementById('submit_btn');
                btn.disabled = true;
                btn.innerText = "กำลังส่งข้อมูลเข้าศูนย์ยุทธการ...";

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
                            radius_meters: radiusMeters,
                            mgrs: currentMGRS,
                            tactical_icon: tacticalIcon,
                            images: validImages
                        })
                    });

                    const data = await res.json();
                    if (res.ok) {
                        alert('✅ บันทึกรายงานและส่งข้อมูลเข้ากลุ่ม LINE สำเร็จ');
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

# --- หน้าศูนย์รวมแผนที่ยุทธศาสตร์ (TACTICAL MAP DASHBOARD) ---
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
                --thai-red: #ff3838;
                --mgrs-green: #00ffcc;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body, html { width: 100%; height: 100%; overflow: hidden; font-family: 'Chakra Petch', sans-serif; background: #060907; }
            #dashboard-map { width: 100%; height: 100%; }

            #auth-gate {
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: linear-gradient(rgba(0,0,0,0.88), rgba(0,0,0,0.96)), url('/bg_new.jpg') center/cover;
                z-index: 99999; display: flex; justify-content: center; align-items: center; padding: 20px;
            }
            .gate-box {
                width: 100%; max-width: 420px; background: rgba(10, 15, 12, 0.95);
                border: 1.5px solid var(--gold-accent); border-radius: 16px; padding: 34px 26px;
                box-shadow: 0 0 40px rgba(212, 175, 55, 0.25); text-align: center; backdrop-filter: blur(14px);
            }
            .gate-title { color: var(--gold-accent); font-size: 21px; font-weight: 700; letter-spacing: 2px; margin-bottom: 6px; }
            .gate-subtitle { font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #8da196; margin-bottom: 24px; letter-spacing: 1px; }
            .gate-input {
                width: 100%; background: rgba(5, 8, 6, 0.9); border: 1.5px solid rgba(212, 175, 55, 0.4);
                border-radius: 10px; color: #fff; padding: 13px; font-size: 18px; text-align: center;
                font-family: 'Chakra Petch', sans-serif; margin-bottom: 18px; outline: none; letter-spacing: 3px;
            }
            .gate-input:focus { border-color: var(--gold-accent); box-shadow: 0 0 15px var(--gold-glow); }
            .gate-btn {
                width: 100%; background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%);
                border: 1px solid var(--gold-accent); color: #000; font-weight: 700; font-size: 14px;
                padding: 13px; border-radius: 10px; cursor: pointer; text-transform: uppercase; letter-spacing: 1.5px;
            }

            .header-bar {
                position: absolute; top: 15px; left: 15px; z-index: 1000;
                background: rgba(10, 15, 12, 0.94); border: 1.5px solid #d4af37;
                border-radius: 12px; padding: 10px 18px; backdrop-filter: blur(8px);
            }
            .header-bar h2 { font-size: 16px; color: #d4af37; letter-spacing: 2px; text-transform: uppercase; margin: 0; }
            .header-bar p { font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #00ffcc; margin: 2px 0 0 0; }

            .map-switch-top {
                position: absolute; top: 15px; right: 15px; z-index: 1000;
                background: rgba(10, 15, 12, 0.94); border: 1.5px solid #d4af37;
                border-radius: 10px; padding: 6px 12px; backdrop-filter: blur(8px);
            }
            .map-switch-top select { background: transparent; border: none; color: #d4af37; font-family: 'Chakra Petch', sans-serif; font-size: 13px; font-weight: 700; cursor: pointer; outline: none; }

            .tactical-filter-bar {
                position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 1000;
                background: rgba(10, 16, 13, 0.95); backdrop-filter: blur(14px);
                border: 1.5px solid rgba(212, 175, 55, 0.4); border-radius: 35px;
                padding: 6px 12px; display: flex; align-items: center; gap: 6px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.85); max-width: 95vw; overflow-x: auto;
            }
            .tactical-filter-bar::-webkit-scrollbar { display: none; }
            .filter-chip {
                background: rgba(25, 38, 30, 0.85); border: 1px solid rgba(212, 175, 55, 0.3);
                color: #cfd8dc; font-size: 12px; font-weight: 600; padding: 6px 12px;
                border-radius: 20px; cursor: pointer; display: flex; align-items: center; gap: 5px; white-space: nowrap; transition: 0.2s;
            }
            .filter-chip.active { background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%); border-color: #fff; color: #000; font-weight: 700; }
            .filter-count { background: rgba(0, 0, 0, 0.4); color: inherit; font-family: 'Share Tech Mono', monospace; font-size: 10px; padding: 1px 6px; border-radius: 10px; }

            .leaflet-popup-content-wrapper {
                background: rgba(10, 15, 12, 0.96) !important; border: 1.5px solid #d4af37 !important;
                border-radius: 12px !important; color: #fff !important; font-family: 'Chakra Petch', sans-serif !important;
                backdrop-filter: blur(12px);
            }
            .leaflet-popup-tip { background: #d4af37 !important; }

            .popup-gallery {
                display: grid; grid-template-columns: repeat(auto-fit, minmax(65px, 1fr));
                gap: 6px; margin-top: 8px; padding-top: 6px; border-top: 1px dashed rgba(212,175,55,0.3);
            }
            .popup-thumb { width: 100%; aspect-ratio: 1 / 1; border-radius: 6px; border: 1px solid rgba(212,175,55,0.4); object-fit: cover; cursor: pointer; }

            #photo-lightbox {
                display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0, 0, 0, 0.92); backdrop-filter: blur(10px); z-index: 100000;
                justify-content: center; align-items: center; padding: 20px;
            }
            #lightbox-img { max-width: 90vw; max-height: 85vh; border-radius: 12px; border: 2px solid var(--gold-accent); }
            
            .custom-tactical-pin { font-size: 20px; text-align: center; filter: drop-shadow(0 2px 5px rgba(0,0,0,0.85)); cursor: pointer; line-height: 20px; }
            .sitrep-box { font-size: 12.5px; line-height: 1.5; color: #d8e2dc; }
            .sitrep-label-red { font-weight: 700; color: var(--thai-red); text-shadow: 0 0 6px rgba(255, 56, 56, 0.4); }

            .edit-box-input {
                width: 100%; background: rgba(5, 8, 6, 0.9); border: 1px solid var(--gold-accent);
                border-radius: 5px; color: #fff; padding: 6px 8px; font-family: 'Chakra Petch', sans-serif; font-size: 12.5px; margin-top: 3px; outline: none;
            }

            .admin-tools { display: flex; gap: 8px; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(212,175,55,0.4); }
            .btn-admin-act { flex: 1; padding: 7px 10px; font-size: 11.5px; font-weight: 700; border-radius: 6px; cursor: pointer; border: 1px solid; text-align: center; }
            .btn-edit { background: rgba(212,175,55,0.2); border-color: var(--gold-accent); color: var(--gold-accent); }
            .btn-save { background: rgba(0,255,204,0.25); border-color: var(--mgrs-green); color: var(--mgrs-green); }
            .btn-cancel { background: rgba(255,255,255,0.1); border-color: #8da196; color: #cfd8dc; }
            .btn-del { background: rgba(229,57,53,0.2); border-color: #e53935; color: #ff6b6b; }
        </style>
    </head>
    <body>
        <div id="auth-gate">
            <div class="gate-box">
                <div style="font-size: 38px; margin-bottom: 8px;">🔒</div>
                <div class="gate-title">RESTRICTED ACCESS</div>
                <div class="gate-subtitle">TACTICAL RADAR OPERATIONS // AUTH REQUIRED</div>
                <input type="password" id="admin_key_input" class="gate-input" autofocus onkeypress="if(event.key==='Enter') verifyAdminKey()">
                <button type="button" class="gate-btn" onclick="verifyAdminKey()">เข้าสู่ศูนย์แผนที่ยุทธศาสตร์</button>
            </div>
        </div>

        <div id="photo-lightbox" onclick="closeLightbox()">
            <img id="lightbox-img" src="" onclick="event.stopPropagation()">
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

        <div class="tactical-filter-bar" id="filter_bar" style="display: none;">
            <div class="filter-chip active" onclick="applyTacticalFilter('ALL', this)">
                <span>🌐 ทั้งหมด</span>
                <span class="filter-count" id="count_ALL">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('🎯', this)">
                <span>🎯 เป้าหมาย</span>
                <span class="filter-count" id="count_🎯">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('⚔️', this)">
                <span>⚔️ จุดปะทะ</span>
                <span class="filter-count" id="count_⚔️">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('🛡️', this)">
                <span>🛡️ ฐานที่มั่น</span>
                <span class="filter-count" id="count_🛡️">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('⚠️', this)">
                <span>⚠️ วัตถุต้องสงสัย</span>
                <span class="filter-count" id="count_⚠️">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('🚁', this)">
                <span>🚁 ลาน ฮ.</span>
                <span class="filter-count" id="count_🚁">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('⛺', this)">
                <span>⛺ จุดตรวจ</span>
                <span class="filter-count" id="count_⛺">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('💧', this)">
                <span>💧 แหล่งเสบียง</span>
                <span class="filter-count" id="count_💧">0</span>
            </div>
            <div class="filter-chip" onclick="applyTacticalFilter('📡', this)">
                <span>📡 สถานีสื่อสาร</span>
                <span class="filter-count" id="count_📡">0</span>
            </div>
        </div>

        <div id="dashboard-map"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            let currentAdminKey = "";
            let currentReportsData = [];
            let activeFilter = "ALL";
            let mapLayersGroup = L.layerGroup();

            const layers = {
                google_sat: L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                esri_sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 }),
                google_road: L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                opentopo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17 })
            };

            const map = L.map('dashboard-map', { attributionControl: false }).setView([14.967565, 102.081882], 12);
            let activeLayer = layers.google_sat;
            activeLayer.addTo(map);
            mapLayersGroup.addTo(map);

            function changeDashboardLayer(k) {
                if (layers[k]) {
                    map.removeLayer(activeLayer);
                    activeLayer = layers[k];
                    activeLayer.addTo(map);
                }
            }

            function openLightbox(url) {
                document.getElementById('lightbox-img').src = url;
                document.getElementById('photo-lightbox').style.display = 'flex';
            }

            function closeLightbox() {
                document.getElementById('photo-lightbox').style.display = 'none';
            }

            async function verifyAdminKey() {
                const key = document.getElementById('admin_key_input').value.trim();
                if (!key) { alert('กรุณากรอกรหัสผ่าน'); return; }

                try {
                    const res = await fetch(`/api/get-all-reports?passcode=${encodeURIComponent(key)}`);
                    if (res.status === 403 || res.status === 401) {
                        alert('❌ รหัสผ่านความปลอดภัยไม่ถูกต้อง! ปฏิเสธการเข้าถึง');
                        return;
                    }
                    const data = await res.json();
                    currentAdminKey = key;

                    document.getElementById('auth-gate').style.display = 'none';
                    document.getElementById('filter_bar').style.display = 'flex';
                    map.invalidateSize();
                    
                    currentReportsData = data;
                    updateFilterCounts(data);
                    renderMapData(data);
                } catch (e) {
                    alert('⚠️ เกิดข้อผิดพลาดในการตรวจสอบสิทธิ์');
                }
            }

            function updateFilterCounts(data) {
                const counts = { 'ALL': data.length, '🎯': 0, '⚔️': 0, '🛡️': 0, '⚠️': 0, '🚁': 0, '⛺': 0, '💧': 0, '📡': 0 };
                data.forEach(item => {
                    const detail = item.detail || "";
                    const match = detail.match(/🎖️ สัญลักษณ์ยุทธวิธี:\s*(\S+)/) || detail.match(/สัญลักษณ์ยุทธวิธี:\s*(\S+)/);
                    if (match) {
                        const emoji = match[1];
                        if (counts[emoji] !== undefined) counts[emoji]++;
                    }
                });
                for (let k in counts) {
                    const el = document.getElementById(`count_${k}`);
                    if (el) el.innerText = counts[k];
                }
            }

            function applyTacticalFilter(emoji, chipElement) {
                activeFilter = emoji;
                document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
                chipElement.classList.add('active');

                let filtered = currentReportsData;
                if (emoji !== 'ALL') {
                    filtered = currentReportsData.filter(item => {
                        const detail = item.detail || "";
                        return detail.includes(`สัญลักษณ์ยุทธวิธี: ${emoji}`) || detail.includes(`🎖️ สัญลักษณ์ยุทธวิธี: ${emoji}`);
                    });
                }
                renderMapData(filtered, true);
            }

            function formatCleanRedDetail(rawDetail) {
                if (!rawDetail) return "";
                return rawDetail
                    .replace(/^[0-9]+\.\s*/gm, '')
                    .replace(/(เวลา:)/g, '<span class="sitrep-label-red">เวลา:</span>')
                    .replace(/(เวลาบันทึก:)/g, '<span class="sitrep-label-red">เวลาบันทึก:</span>')
                    .replace(/(สัญลักษณ์ยุทธวิธี:)/g, '<span class="sitrep-label-red">สัญลักษณ์ยุทธวิธี:</span>')
                    .replace(/(รัศมีอันตราย:)/g, '<span class="sitrep-label-red">รัศมีอันตราย:</span>')
                    .replace(/(สถานการณ์:)/g, '<span class="sitrep-label-red">สถานการณ์:</span>')
                    .replace(/(เหตุการณ์:)/g, '<span class="sitrep-label-red">เหตุการณ์:</span>')
                    .replace(/(การปฏิบัติ:)/g, '<span class="sitrep-label-red">การปฏิบัติ:</span>')
                    .replace(/(พิกัด MGRS:)/g, '<span class="sitrep-label-red">พิกัด MGRS:</span>')
                    .replace(/(พิกัด GPS:)/g, '<span class="sitrep-label-red">พิกัด GPS:</span>')
                    .replace(/(แผนที่ Google:)/g, '<span class="sitrep-label-red">แผนที่ Google:</span>')
                    .replace(/(จำนวนภาพถ่าย:)/g, '<span class="sitrep-label-red">จำนวนภาพถ่าย:</span>');
            }

            function extractField(detail, fieldName) {
                const regex = new RegExp(`(?:[0-9]+\\.\\s*)?${fieldName}:\\s*(.*)`);
                return detail.match(regex)?.[1] || "";
            }

            function renderMapData(data, autoZoom = false) {
                mapLayersGroup.clearLayers();

                if (data && data.length > 0) {
                    document.getElementById('total_reports').innerText = `แสดงรายงาน: ${data.length} จุด (ตัวกรอง: ${activeFilter})`;
                    const group = [];

                    data.forEach(item => {
                        if (item.latitude && item.longitude) {
                            const detail = item.detail || "";
                            let emoji = "🎯";
                            const match = detail.match(/🎖️ สัญลักษณ์ยุทธวิธี:\s*(\S+)/) || detail.match(/สัญลักษณ์ยุทธวิธี:\s*(\S+)/);
                            if (match) emoji = match[1];

                            const rMatch = detail.match(/⭕ รัศมีอันตราย:\s*(\d+)\s*เมตร/) || detail.match(/รัศมีอันตราย:\s*(\d+)\s*เมตร/);
                            if (rMatch) {
                                const radiusMeters = parseInt(rMatch[1]);
                                if (radiusMeters > 0) {
                                    L.circle([item.latitude, item.longitude], {
                                        radius: radiusMeters, color: '#ff3b30', fillColor: '#ff3b30',
                                        fillOpacity: 0.2, weight: 1.5, dashArray: '4, 6'
                                    }).addTo(mapLayersGroup);
                                }
                            }

                            const customIcon = L.divIcon({
                                className: 'custom-tactical-pin', html: emoji,
                                iconSize: [22, 22], iconAnchor: [11, 11]
                            });

                            const marker = L.marker([item.latitude, item.longitude], { icon: customIcon }).addTo(mapLayersGroup);
                            
                            let galleryHtml = "";
                            if (item.image_url && item.image_url.trim() !== "") {
                                const imgUrls = item.image_url.split(",").map(u => u.trim()).filter(u => u !== "");
                                if (imgUrls.length > 0) {
                                    const thumbs = imgUrls.map(url => `
                                        <img src="${url}" class="popup-thumb" onclick="openLightbox('${url}')" title="แตะเพื่อดูภาพขนาดใหญ่">
                                    `).join("");
                                    galleryHtml = `<div class="popup-gallery">${thumbs}</div>`;
                                }
                            }

                            const cleanFormattedHtml = formatCleanRedDetail(detail);

                            marker.bindPopup(`
                                <div style="min-width: 250px; max-width: 330px;" class="sitrep-box" id="popup_content_${item.id}">
                                    <div style="font-size:15px; font-weight:bold; color:#d4af37; margin-bottom:8px; border-bottom:1px solid #d4af37; padding-bottom:4px;">
                                        ${emoji} รายงานสถานการณ์ยุทธวิธี
                                    </div>
                                    <div id="view_mode_${item.id}">
                                        <div style="white-space: pre-line; color:#e0e6ed; line-height:1.5;">${cleanFormattedHtml}</div>
                                        ${galleryHtml}
                                        <div class="admin-tools">
                                            <button class="btn-admin-act btn-edit" onclick="enableEditMode(${item.id})">✏️ แก้ไขข้อมูล</button>
                                            <button class="btn-admin-act btn-del" onclick="deleteReportPrompt(${item.id})">🗑️ ลบ</button>
                                        </div>
                                    </div>
                                    <div id="edit_mode_${item.id}" style="display: none;">
                                        <div style="margin-bottom: 8px;">
                                            <span class="sitrep-label-red">สถานการณ์:</span>
                                            <input type="text" id="edit_sit_${item.id}" class="edit-box-input" value="${extractField(detail, 'สถานการณ์')}">
                                        </div>
                                        <div style="margin-bottom: 8px;">
                                            <span class="sitrep-label-red">เหตุการณ์:</span>
                                            <textarea id="edit_inc_${item.id}" class="edit-box-input" rows="2">${extractField(detail, 'เหตุการณ์')}</textarea>
                                        </div>
                                        <div style="margin-bottom: 8px;">
                                            <span class="sitrep-label-red">การปฏิบัติ:</span>
                                            <textarea id="edit_act_${item.id}" class="edit-box-input" rows="2">${extractField(detail, 'การปฏิบัติ')}</textarea>
                                        </div>
                                        <div class="admin-tools">
                                            <button class="btn-admin-act btn-save" onclick="saveEditedReport(${item.id})">💾 ตกลงบันทึก</button>
                                            <button class="btn-admin-act btn-cancel" onclick="cancelEditMode(${item.id})">ยกเลิก</button>
                                        </div>
                                    </div>
                                </div>
                            `);
                            group.push([item.latitude, item.longitude]);
                        }
                    });

                    if (group.length > 0 && (autoZoom || group.length === currentReportsData.length)) {
                        map.fitBounds(group, { padding: [50, 50], maxZoom: 16 });
                    }
                } else {
                    document.getElementById('total_reports').innerText = `ไม่พบจุดรายงานสำหรับตัวกรอง: ${activeFilter}`;
                }
            }

            function enableEditMode(id) {
                document.getElementById(`view_mode_${id}`).style.display = "none";
                document.getElementById(`edit_mode_${id}`).style.display = "block";
            }

            function cancelEditMode(id) {
                document.getElementById(`view_mode_${id}`).style.display = "block";
                document.getElementById(`edit_mode_${id}`).style.display = "none";
            }

            async function saveEditedReport(reportId) {
                const newSit = document.getElementById(`edit_sit_${reportId}`).value.trim();
                const newInc = document.getElementById(`edit_inc_${reportId}`).value.trim();
                const newAct = document.getElementById(`edit_act_${reportId}`).value.trim();

                const editPass = prompt("🔑 กรุณากรอกรหัสผ่านเพื่อยืนยันการแก้ไขข้อมูล (wisarut):");
                if (editPass === null) return;

                if (editPass !== "wisarut") {
                    alert("❌ รหัสผ่านไม่ถูกต้อง! ไม่สามารถแก้ไขข้อมูลได้");
                    return;
                }

                try {
                    const res = await fetch('/api/update-report', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            passcode: editPass,
                            report_id: reportId,
                            situation: newSit,
                            incident: newInc,
                            action: newAct
                        })
                    });
                    if (res.ok) {
                        alert('✅ แก้ไขข้อมูลและบันทึกสำเร็จ');
                        verifyAdminKey();
                    } else {
                        const err = await res.json();
                        alert('❌ ' + (err.detail || 'ไม่สามารถแก้ไขข้อมูลได้'));
                    }
                } catch(e) {
                    alert('⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อเพื่อแก้ไขข้อมูล');
                }
            }

            async function deleteReportPrompt(reportId) {
                const editPass = prompt("🔑 กรุณากรอกรหัสผ่านเพื่อยืนยันการลบจุดรายงาน (wisarut):");
                if (editPass === null) return;

                if (editPass !== "wisarut") {
                    alert("❌ รหัสผ่านไม่ถูกต้อง! ปฏิเสธการลบข้อมูล");
                    return;
                }

                try {
                    const res = await fetch('/api/delete-report', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            passcode: editPass,
                            report_id: reportId
                        })
                    });
                    if (res.ok) {
                        alert('✅ ลบจุดรายงานสำเร็จ');
                        verifyAdminKey();
                    } else {
                        alert('❌ ไม่สามารถลบข้อมูลได้');
                    }
                } catch(e) {
                    alert('⚠️ เกิดข้อผิดพลาดในการลบข้อมูล');
                }
            }
        </script>
    </body>
    </html>
    """

# API สำหรับดึงรายงานทั้งหมด
@app.get("/api/get-all-reports")
def get_all_reports(passcode: str = ""):
    if passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=403, detail="สิทธิ์การเข้าถึงไม่ถูกต้อง")

    try:
        response = supabase.table("reports").select("*").order("created_at", desc=True).limit(100).execute()
        return response.data
    except Exception as e:
        print(f"Fetch all error: {e}")
        return []

# API แก้ไขรายงาน
@app.post("/api/update-report")
def update_report(payload: UpdateReportPayload):
    if payload.passcode != EDIT_PASSCODE:
        raise HTTPException(status_code=403, detail="รหัสผ่านยืนยันการแก้ไขไม่ถูกต้อง")

    try:
        res = supabase.table("reports").select("*").eq("id", payload.report_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="ไม่พบรายงาน")

        old_detail = res.data[0].get("detail", "")
        new_detail = re.sub(r"(?:[0-9]+\.\s*)?สถานการณ์:\s*.*", f"สถานการณ์: {payload.situation}", old_detail)
        new_detail = re.sub(r"(?:[0-9]+\.\s*)?เหตุการณ์:\s*.*", f"เหตุการณ์: {payload.incident}", new_detail)
        new_detail = re.sub(r"(?:[0-9]+\.\s*)?การปฏิบัติ:\s*.*", f"การปฏิบัติ: {payload.action}", new_detail)

        supabase.table("reports").update({"detail": new_detail}).eq("id", payload.report_id).execute()
        return {"status": "updated"}
    except Exception as e:
        print(f"Update error: {e}")
        raise HTTPException(status_code=500, detail="ไม่สามารถอัปเดตข้อมูลได้")

# API ลบรายงาน
@app.post("/api/delete-report")
def delete_report(payload: DeleteReportPayload):
    if payload.passcode != EDIT_PASSCODE:
        raise HTTPException(status_code=403, detail="รหัสผ่านยืนยันการลบไม่ถูกต้อง")

    try:
        supabase.table("reports").delete().eq("id", payload.report_id).execute()
        return {"status": "deleted"}
    except Exception as e:
        print(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail="ไม่สามารถลบข้อมูลได้")

# --- ฟังก์ชันสร้างการ์ด Flex Message และยิงเข้า LINE กลุ่มอัตโนมัติ ---
def send_tactical_flex_to_line(payload: ReportPayload, time_str: str, image_urls: list):
    if not CHANNEL_ACCESS_TOKEN:
        return

    target_id = TARGET_GROUP_ID
    if not target_id:
        try:
            grp_res = supabase.table("line_groups").select("group_id").order("created_at", desc=True).limit(1).execute()
            if grp_res.data and len(grp_res.data) > 0:
                target_id = grp_res.data[0].get("group_id")
        except Exception as e:
            print(f"Fetch target group error: {e}")

    if not target_id:
        print("⚠️ ไม่พบ LINE Group ID สำหรับยิงข้อความ (กรุณาดึงบอทเข้ากลุ่มแล้วพิมพ์ .id)")
        return

    icon_emoji = payload.tactical_icon.split(" ")[0] if payload.tactical_icon else "🎯"
    mgrs_val = payload.mgrs if payload.mgrs else "N/A"
    first_img = image_urls[0] if image_urls else None

    flex_json = {
        "type": "bubble",
        "size": "mega",
        "styles": {
            "header": {"backgroundColor": "#0d1410"},
            "body": {"backgroundColor": "#060a08"},
            "footer": {"backgroundColor": "#0d1410"}
        },
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "PHANTOM SITREP FEED", "weight": "bold", "color": "#d4af37", "size": "xs", "flex": 1},
                        {"type": "text", "text": "FLASH // PRIORITY", "weight": "bold", "color": "#ff3838", "size": "xxs", "align": "end"}
                    ]
                },
                {"type": "text", "text": f"{icon_emoji} {payload.situation}", "weight": "bold", "color": "#ffffff", "size": "md", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "เวลาบันทึก:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3},
                        {"type": "text", "text": time_str, "color": "#e0e6ed", "size": "xs", "flex": 7}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "สัญลักษณ์:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3},
                        {"type": "text", "text": payload.tactical_icon, "color": "#e0e6ed", "size": "xs", "flex": 7}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "พิกัด MGRS:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3},
                        {"type": "text", "text": mgrs_val, "color": "#00ffcc", "size": "xs", "weight": "bold", "flex": 7}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "พิกัด GPS:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3},
                        {"type": "text", "text": f"{payload.latitude:.6f}, {payload.longitude:.6f}", "color": "#7ee0ad", "size": "xs", "flex": 7}
                    ]
                },
                {"type": "separator", "color": "#334139", "margin": "md"},
                {"type": "text", "text": "เหตุการณ์:", "color": "#ff3838", "size": "xs", "weight": "bold", "margin": "sm"},
                {"type": "text", "text": payload.incident, "color": "#e0e6ed", "size": "xs", "wrap": True},
                {"type": "text", "text": "การปฏิบัติ:", "color": "#ff3838", "size": "xs", "weight": "bold", "margin": "sm"},
                {"type": "text", "text": payload.action, "color": "#e0e6ed", "size": "xs", "wrap": True}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#d4af37",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "🌐 แผนที่เรดาร์รวม",
                        "uri": "https://tactical-line-backend.onrender.com/map"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "color": "#223328",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "📍 นำทาง Maps",
                        "uri": f"https://maps.google.com/?q={payload.latitude},{payload.longitude}"
                    }
                }
            ]
        }
    }

    if first_img:
        flex_json["hero"] = {
            "type": "image",
            "url": first_img,
            "size": "full",
            "aspectRatio": "16:9",
            "aspectMode": "cover"
        }

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            flex_container = FlexContainer.from_dict(flex_json)
            push_req = PushMessageRequest(
                to=target_id,
                messages=[FlexMessage(alt_text=f"🚨 รายงานยุทธวิธี: {payload.situation}", contents=flex_container)]
            )
            line_bot_api.push_message(push_req)
            print(f"✅ ส่ง LINE Flex Message เข้ากลุ่ม {target_id} สำเร็จ")
    except Exception as e:
        print(f"❌ LINE Push Message Error: {e}")

# API รับรายงานจากหน้าฟอร์ม
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

    all_images_str = ",".join(uploaded_image_urls) if uploaded_image_urls else None
    mgrs_str = payload.mgrs if payload.mgrs else "N/A"
    radius_val = payload.radius_meters or 0

    try:
        report_data = {
            "user_id": payload.user_id,
            "report_type": "รายงานยุทธวิธี (PHANTOM HUD)",
            "detail": (
                f"เวลา: {time_str}\n"
                f"สัญลักษณ์ยุทธวิธี: {payload.tactical_icon}\n"
                f"รัศมีอันตราย: {radius_val} เมตร\n"
                f"สถานการณ์: {payload.situation}\n"
                f"เวลาบันทึก: {time_str}\n"
                f"เหตุการณ์: {payload.incident}\n"
                f"พิกัด MGRS: {mgrs_str}\n"
                f"พิกัด GPS: {payload.latitude:.6f}, {payload.longitude:.6f}\n"
                f"การปฏิบัติ: {payload.action}\n"
                f"แผนที่ Google: https://maps.google.com/?q={payload.latitude},{payload.longitude}\n"
                f"จำนวนภาพถ่าย: {len(uploaded_image_urls)} ภาพ"
            ),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "image_url": all_images_str
        }
        supabase.table("reports").insert(report_data).execute()

        # ส่งการ์ดรายงานยุทธวิธีเข้ากลุ่ม LINE
        send_tactical_flex_to_line(payload, time_str, uploaded_image_urls)

    except Exception as err:
        print(f"Supabase error: {err}")
        raise HTTPException(status_code=500, detail="ไม่สามารถบันทึกข้อมูลลงฐานข้อมูลได้")

    return {"status": "success", "time": time_str, "images_count": len(uploaded_image_urls)}

# Webhook Callback สำหรับรับ Event จาก LINE
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Webhook error: {e}")

    return Response(content="OK", status_code=200)

@handler.add(JoinEvent)
def handle_join(event):
    if event.source.type == "group":
        grp_id = event.source.group_id
        try:
            supabase.table("line_groups").upsert({"group_id": grp_id, "group_name": "TACTICAL_GROUP"}).execute()
        except Exception as e:
            print(f"Save group id error: {e}")

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    if event.source.type == "group":
        grp_id = event.source.group_id
        if text.lower() == ".id":
            try:
                supabase.table("line_groups").upsert({"group_id": grp_id, "group_name": "TACTICAL_GROUP"}).execute()
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.reply_message_with_http_info(
                        reply_message_request={
                            "replyToken": event.reply_token,
                            "messages": [TextMessage(text=f"🎯 บันทึก Group ID เข้าศูนย์ยุทธการเรียบร้อย:\n{grp_id}")]
                        }
                    )
            except Exception as e:
                print(f"Reply error: {e}")
