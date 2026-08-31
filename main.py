import os
import re
import uuid
import base64
import math
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

class FireSupportPayload(BaseModel):
    passcode: str
    target_name: str
    weapon_type: str
    gun_coords: str
    gun_mgrs: str
    target_coords: str
    target_mgrs: str
    distance_meters: float
    azimuth_deg: float
    azimuth_mils: float
    qe_mils: float
    tof_seconds: int
    image_base64: Optional[str] = None

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
                margin: 0; padding: 16px 12px; font-family: 'Chakra Petch', sans-serif;
                background-color: #060907;
                background-image: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.7)), url('/bg_new.jpg');
                background-size: cover; background-position: center center; background-attachment: fixed;
                color: #e2e8e5; min-height: 100vh; display: flex; justify-content: center; align-items: center;
            }
            .hud-container {
                width: 100%; max-width: 520px;
                background-image: linear-gradient(rgba(10, 15, 12, 0.85), rgba(6, 10, 8, 0.92)), url('/bg.jpg');
                background-size: cover; background-position: center center;
                border: 1.5px solid var(--border-subtle); border-radius: 16px;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9), 0 0 25px rgba(212, 175, 55, 0.15);
                padding: 24px 20px; position: relative; overflow: hidden;
            }
            .thai-ribbon {
                position: absolute; top: 0; right: 0; width: 90px; height: 4px;
                background: linear-gradient(90deg, var(--thai-red) 0% 20%, #fff 20% 40%, var(--thai-blue) 40% 60%, #fff 60% 80%, var(--thai-red) 80% 100%);
            }
            .header-badge { text-align: center; margin-bottom: 18px; position: relative; }
            .title-main { font-size: 21px; font-weight: 700; color: var(--gold-accent); letter-spacing: 2.5px; text-transform: uppercase; margin: 0; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9); }
            .title-sub { font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #8da196; letter-spacing: 1.2px; margin-top: 3px; }
            .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            .form-group { margin-bottom: 12px; }
            label { display: block; font-size: 12.5px; font-weight: 600; color: #a2b5aa; margin-bottom: 5px; letter-spacing: 0.5px; }
            input, textarea, select {
                width: 100%; background-image: linear-gradient(rgba(5, 8, 6, 0.8), rgba(5, 8, 6, 0.9)), url('/bg.jpg');
                background-size: cover; background-position: center; border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px; color: #ffffff; padding: 10px 12px; font-family: 'Chakra Petch', sans-serif; font-size: 14px;
            }
            input:focus, textarea:focus, select:focus { outline: none; border-color: var(--gold-accent); box-shadow: 0 0 12px var(--gold-glow); }
            .readonly-input { font-family: 'Share Tech Mono', monospace; color: #7ee0ad; background: #000; }
            .mgrs-input { font-family: 'Share Tech Mono', monospace; color: var(--mgrs-green) !important; font-weight: 700; letter-spacing: 1.2px; }
            textarea { resize: vertical; min-height: 55px; }
            .gps-tools { display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 8px; margin-top: 6px; }
            .tool-btn {
                background: linear-gradient(180deg, rgba(30, 42, 35, 0.9) 0%, rgba(15, 22, 18, 0.9) 100%);
                border: 1px solid rgba(212, 175, 55, 0.35); color: var(--gold-accent); padding: 9px 6px; font-size: 12px; font-weight: 600; border-radius: 8px; cursor: pointer; text-align: center; display: flex; align-items: center; justify-content: center; gap: 4px;
            }
            .tool-btn.highlight { border-color: var(--gold-accent); background: rgba(212, 175, 55, 0.25); }
            #map-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 10000; opacity: 0; transition: opacity 0.25s; }
            #map-modal.show { display: flex; opacity: 1; }
            .map-app-container { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
            #tactical-map { position: absolute; top: 0; left: 0; right: 0; bottom: 0; width: 100%; height: 100%; z-index: 1; }
            .map-top-bar { position: absolute; top: 15px; left: 15px; right: 15px; z-index: 1000; display: flex; flex-direction: column; gap: 8px; }
            .map-top-row { display: flex; gap: 8px; }
            .search-box-wrapper { flex: 1; background: rgba(18, 24, 20, 0.94); border: 1px solid rgba(212, 175, 55, 0.4); border-radius: 25px; display: flex; align-items: center; padding: 4px 14px; }
            .search-box-wrapper input { background: transparent; border: none; padding: 6px 8px; font-size: 14px; color: #fff; }
            .btn-circle-icon { width: 44px; height: 44px; border-radius: 50%; background: rgba(18, 24, 20, 0.94); border: 1px solid rgba(212, 175, 55, 0.4); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 16px; cursor: pointer; }
            .provider-selector-bar { background: rgba(18, 24, 20, 0.94); border: 1px solid rgba(212, 175, 55, 0.4); border-radius: 10px; padding: 4px 10px; }
            .provider-selector-bar select { background: transparent; border: none; color: var(--gold-accent); font-size: 12.5px; font-weight: 600; }
            .map-floating-controls { position: absolute; right: 15px; bottom: 180px; z-index: 1000; }
            .center-pin-marker { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -100%); z-index: 100; pointer-events: none; text-align: center; }
            .center-pin-marker.dragging { transform: translate(-50%, -120%) scale(1.1); }
            .pin-emoji-badge { font-size: 24px; filter: drop-shadow(0 3px 6px rgba(0,0,0,0.8)); }
            .pin-shadow { position: absolute; bottom: -2px; left: 50%; transform: translateX(-50%); width: 12px; height: 4px; background: rgba(0,0,0,0.6); border-radius: 50%; filter: blur(1px); }
            .map-bottom-sheet { position: absolute; bottom: 15px; left: 15px; right: 15px; z-index: 1000; background: rgba(12, 18, 14, 0.95); border: 1.5px solid var(--border-subtle); border-radius: 16px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
            .sheet-row-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
            .radius-control-bar { display: flex; align-items: center; gap: 8px; border-top: 1px solid rgba(212, 175, 55, 0.2); padding-top: 8px; }
            .radius-control-bar label { font-size: 11.5px; color: #ff6b6b; font-weight: 700; margin: 0; white-space: nowrap; }
            .radius-control-bar select { background: rgba(0,0,0,0.6); border: 1px solid rgba(255, 107, 107, 0.4); color: #ff6b6b; padding: 5px 8px; font-size: 12px; font-weight: bold; border-radius: 6px; flex: 1; }
            .coord-info-title { font-size: 11px; color: #8da196; text-transform: uppercase; }
            .coord-info-val { font-family: 'Share Tech Mono', monospace; font-size: 13.5px; font-weight: 700; color: #7ee0ad; }
            .coord-mgrs-val { font-family: 'Share Tech Mono', monospace; font-size: 13.5px; font-weight: 700; color: var(--mgrs-green); }
            .btn-confirm-pin { background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%); border: 1px solid var(--gold-accent); color: #000; font-weight: 700; font-size: 13px; padding: 10px 18px; border-radius: 10px; cursor: pointer; text-transform: uppercase; }
            .img-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 6px; }
            .img-slot { aspect-ratio: 1 / 1; border: 1px dashed rgba(212, 175, 55, 0.4); border-radius: 7px; display: flex; align-items: center; justify-content: center; cursor: pointer; overflow: hidden; position: relative; }
            .img-slot img { width: 100%; height: 100%; object-fit: cover; }
            .img-slot span { font-size: 20px; color: var(--gold-accent); }
            .btn-remove-img { position: absolute; top: 2px; right: 2px; background: rgba(165, 28, 36, 0.88); color: #fff; border-radius: 50%; width: 18px; height: 18px; font-size: 11px; line-height: 16px; text-align: center; cursor: pointer; display: none; }
            .img-slot.has-img .btn-remove-img { display: block; }
            .btn-action { width: 100%; background: linear-gradient(180deg, #d4af37 0%, #7d6017 100%); border: 1px solid var(--gold-accent); color: #000; padding: 13px; font-size: 15px; font-weight: 700; letter-spacing: 2px; cursor: pointer; border-radius: 10px; margin-top: 15px; text-transform: uppercase; }
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
                    <option value="0">0 ม. (ไม่ระบุรัศมี)</option>
                    <option value="50">50 เมตร (ประชิด)</option>
                    <option value="100">100 เมตร (ยิงสนับสนุน)</option>
                    <option value="250">250 เมตร (ค. / IED)</option>
                    <option value="500">500 เมตร (ปิดล้อม)</option>
                    <option value="1000">1,000 เมตร (1 กม.)</option>
                    <option value="5000">5,000 เมตร (5 กม.)</option>
                    <option value="10000">10,000 เมตร (10 กม.)</option>
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
                <textarea id="incident" rows="2" placeholder="ระบุรายละเอียดสิ่งที่ตรวจพบ"></textarea>
            </div>
            <div class="form-group">
                <label>การปฏิบัติ:</label>
                <textarea id="action" rows="2" placeholder="ระบุการวางกำลังและการปฏิบัติ"></textarea>
            </div>
            <div class="form-group">
                <label>📷 ภาพถ่ายพื้นที่ปฏิบัติการ (สูงสุด 5 ภาพ):</label>
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
                            <input type="text" id="map_search_input" placeholder="ค้นหา: พิกัด / MGRS / ชื่อสถานที่..." onkeypress="if(event.key==='Enter') searchLocation()">
                            <button type="button" onclick="searchLocation()" style="background:transparent; border:none; color:var(--gold-accent); cursor:pointer; font-weight:bold; font-size:12px; margin-left:4px;">ค้นหา</button>
                        </div>
                        <div class="btn-circle-icon" onclick="closeMapModal()" style="color:#ff6b6b; font-size:18px;">✕</div>
                    </div>
                    <div class="provider-selector-bar">
                        <select id="map_provider_select" onchange="changeMapProvider(this.value)">
                            <option value="google_sat">🌐 Google Maps - ภาพถ่ายดาวเทียม</option>
                            <option value="esri_sat">🛰️ ESRI World Imagery - ทหาร</option>
                            <option value="google_road">🗺️ Google Maps - ถนน</option>
                            <option value="opentopo">⛰️ OpenTopoMap - ภูมิประเทศ</option>
                        </select>
                    </div>
                </div>
                <div class="map-floating-controls">
                    <div class="btn-circle-icon" onclick="locateUserOnMap()" title="ล็อกตำแหน่งตัวเอง">🎯</div>
                </div>
                <div class="map-bottom-sheet">
                    <div class="sheet-row-top">
                        <div>
                            <div class="coord-info-title" id="sheet_symbol_title">🎯 เป้าหมาย</div>
                            <div class="coord-info-val" id="sheet_coords">14.967565, 102.081882</div>
                            <div class="coord-mgrs-val" id="sheet_mgrs">MGRS: คำนวณ...</div>
                        </div>
                        <button type="button" class="btn-confirm-pin" onclick="confirmCenterPin()">ปักหมุดจุดนี้</button>
                    </div>
                    <div class="radius-control-bar">
                        <label>⭕ รัศมีอันตราย:</label>
                        <select id="modal_radius_select" onchange="updateModalRadiusCircle(this.value)">
                            <option value="0">0 ม.</option>
                            <option value="50">50 เมตร</option>
                            <option value="100">100 เมตร</option>
                            <option value="500">500 เมตร</option>
                            <option value="1000">1,000 เมตร (1 กม.)</option>
                            <option value="5000">5,000 เมตร (5 กม.)</option>
                        </select>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/mgrs@1.0.0/dist/mgrs.min.js"></script>
        <script>
            let userLat = 14.967565, userLon = 102.081882, currentPinLat = 14.967565, currentPinLon = 102.081882, currentMGRS = "";
            let imagesArray = [null, null, null, null, null], activeSlotIndex = 0, map, currentLayer, radiusCircle;
            const mapLayers = {
                google_sat: L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                esri_sat: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 }),
                google_road: L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'] }),
                opentopo: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', { maxZoom: 17 })
            };
            function updateTime() { document.getElementById('time_display').value = new Date().toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' }); }
            updateTime();
            function updatePinIconPreview() {
                const sel = document.getElementById('tactical_icon').value;
                document.getElementById('marker_emoji_preview').innerText = sel.split(' ')[0];
                document.getElementById('sheet_symbol_title').innerText = sel;
            }
            function convertToMGRS(lat, lon) {
                try {
                    if (typeof mgrs !== 'undefined' && mgrs.forward) {
                        const raw = mgrs.forward([lon, lat], 5);
                        return raw.length >= 15 ? `${raw.slice(0, 3)} ${raw.slice(3, 5)} ${raw.slice(5, 10)} ${raw.slice(10, 15)}` : raw;
                    }
                } catch(e) {}
                return "N/A";
            }
            function getAutoGPS() {
                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(pos => {
                        userLat = pos.coords.latitude; userLon = pos.coords.longitude;
                        currentPinLat = userLat; currentPinLon = userLon;
                        updateCoordsDisplay();
                        document.getElementById('gps_status').innerText = "⚡ GPS: ล็อกพิกัดแล้ว";
                    }, () => { document.getElementById('gps_status').innerText = "⚠️ GPS: ออฟไลน์"; }, { enableHighAccuracy: true });
                }
            }
            getAutoGPS();
            function updateCoordsDisplay() {
                document.getElementById('coords_display').value = `${userLat.toFixed(6)}, ${userLon.toFixed(6)}`;
                currentMGRS = convertToMGRS(userLat, userLon);
                document.getElementById('mgrs_display').value = currentMGRS;
            }
            function manualCoordsInput(val) {
                const p = val.split(',');
                if (p.length === 2) {
                    const lat = parseFloat(p[0]), lon = parseFloat(p[1]);
                    if (!isNaN(lat) && !isNaN(lon)) { userLat = lat; userLon = lon; currentPinLat = lat; currentPinLon = lon; updateCoordsDisplay(); }
                }
            }
            function updateModalRadiusCircle(r) {
                const dist = parseInt(r);
                if (radiusCircle) map.removeLayer(radiusCircle);
                if (dist > 0 && map) radiusCircle = L.circle([currentPinLat, currentPinLon], { radius: dist, color: '#ff3b30', fillColor: '#ff3b30', fillOpacity: 0.22 }).addTo(map);
                document.getElementById('danger_radius').value = r;
            }
            function initInteractiveMap() {
                updatePinIconPreview();
                if (!map) {
                    map = L.map('tactical-map', { zoomControl: false, attributionControl: false }).setView([currentPinLat, currentPinLon], 16);
                    currentLayer = mapLayers.google_sat; currentLayer.addTo(map);
                    map.on('move', () => {
                        const c = map.getCenter();
                        currentPinLat = c.lat; currentPinLon = c.lng;
                        document.getElementById('sheet_coords').innerText = `${currentPinLat.toFixed(6)}, ${currentPinLon.toFixed(6)}`;
                        document.getElementById('sheet_mgrs').innerText = `MGRS: ${convertToMGRS(currentPinLat, currentPinLon)}`;
                        if (radiusCircle) radiusCircle.setLatLng(c);
                    });
                } else { map.setView([currentPinLat, currentPinLon], 16); }
            }
            function changeMapProvider(k) { if (map && mapLayers[k]) { map.removeLayer(currentLayer); currentLayer = mapLayers[k]; currentLayer.addTo(map); } }
            function openMapModal() { document.getElementById('map-modal').classList.add('show'); setTimeout(() => { initInteractiveMap(); map.invalidateSize(); }, 150); }
            function closeMapModal() { document.getElementById('map-modal').classList.remove('show'); }
            function locateUserOnMap() { if (navigator.geolocation) navigator.geolocation.getCurrentPosition(p => map.flyTo([p.coords.latitude, p.coords.longitude], 17)); }
            async function searchLocation() {
                const q = document.getElementById('map_search_input').value.trim();
                if (!q) return;
                try {
                    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&countrycodes=th`);
                    const data = await res.json();
                    if (data.length > 0) map.flyTo([parseFloat(data[0].lat), parseFloat(data[0].lon)], 16);
                    else alert('ไม่พบสถานที่');
                } catch(e) { alert('ค้นหาล้มเหลว'); }
            }
            function confirmCenterPin() { userLat = currentPinLat; userLon = currentPinLon; updateCoordsDisplay(); closeMapModal(); }
            function triggerSlotUpload(i) { activeSlotIndex = i; document.getElementById('single_file_input').click(); }
            function handleSingleFile(files) {
                if (files[0]) {
                    const reader = new FileReader();
                    reader.onload = (e) => { imagesArray[activeSlotIndex] = e.target.result; renderSlot(activeSlotIndex); updateImgCount(); };
                    reader.readAsDataURL(files[0]);
                }
                document.getElementById('single_file_input').value = "";
            }
            function removeImage(e, i) { e.stopPropagation(); imagesArray[i] = null; renderSlot(i); updateImgCount(); }
            function renderSlot(i) {
                const s = document.getElementById(`slot-${i}`);
                if (imagesArray[i]) s.innerHTML = `<img src="${imagesArray[i]}"><div class="btn-remove-img" onclick="removeImage(event, ${i})">✕</div>`;
                else s.innerHTML = `<span>+</span><div class="btn-remove-img" onclick="removeImage(event, ${i})">✕</div>`;
            }
            function updateImgCount() { document.getElementById('img_count').innerText = `แนบภาพ: ${imagesArray.filter(Boolean).length} / 5 ภาพ`; }
            async function submitReport() {
                const passcode = document.getElementById('passcode').value, situation = document.getElementById('situation').value;
                if (!passcode) { alert('กรุณากรอกรหัสผ่าน'); return; }
                const btn = document.getElementById('submit_btn'); btn.disabled = true; btn.innerText = "กำลังส่ง...";
                try {
                    const res = await fetch('/api/submit-report', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ passcode, situation, incident: document.getElementById('incident').value, action: document.getElementById('action').value, latitude: userLat, longitude: userLon, radius_meters: parseInt(document.getElementById('danger_radius').value), mgrs: currentMGRS, tactical_icon: document.getElementById('tactical_icon').value, images: imagesArray.filter(Boolean) })
                    });
                    if (res.ok) { alert('ส่งรายงานสำเร็จ'); location.reload(); }
                    else { alert('รหัสผ่านไม่ถูกต้อง'); btn.disabled = false; btn.innerText = "ส่งรายงานยุทธวิธี"; }
                } catch(e) { alert('เชื่อมต่อล้มเหลว'); btn.disabled = false; btn.innerText = "ส่งรายงานยุทธวิธี"; }
            }
        </script>
    </body>
    </html>
    """

# --- หน้าศูนย์รวมแผนที่ยุทธศาสตร์ (Combat Operations Center พร้อมระบบ CFF ที่แก้ไขเสร็จสมบูรณ์) ---
@app.get("/map", response_class=HTMLResponse)
def get_map_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PHANTOM - COMBAT OPERATIONS CENTER</title>
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

            .dashboard-search-container {
                position: absolute; top: 15px; left: 50%; transform: translateX(-50%); z-index: 1000;
                background: rgba(10, 16, 13, 0.96); backdrop-filter: blur(14px);
                border: 1.5px solid rgba(212, 175, 55, 0.5); border-radius: 30px;
                padding: 4px 16px; display: flex; align-items: center; box-shadow: 0 6px 25px rgba(0,0,0,0.8);
                width: 90%; max-width: 450px;
            }
            .dashboard-search-container input {
                background: transparent; border: none; outline: none; color: #fff;
                font-family: 'Chakra Petch', sans-serif; font-size: 14px; padding: 8px; flex: 1;
            }
            .dashboard-search-container button {
                background: linear-gradient(180deg, #d4af37 0%, #9a7b1c 100%);
                border: none; border-radius: 20px; color: #000; font-weight: 700;
                padding: 6px 16px; font-size: 12px; cursor: pointer; text-transform: uppercase;
            }

            .map-switch-top {
                position: absolute; top: 15px; right: 15px; z-index: 1000;
                background: rgba(10, 15, 12, 0.94); border: 1.5px solid #d4af37;
                border-radius: 10px; padding: 6px 12px; backdrop-filter: blur(8px);
            }
            .map-switch-top select { background: transparent; border: none; color: #d4af37; font-family: 'Chakra Petch', sans-serif; font-size: 13px; font-weight: 700; cursor: pointer; outline: none; }

            /* --- ฝั่งซ้าย: รวมแผงควบคุมทั้งหมด พับเก็บได้ --- */
            .left-sidebar-container {
                position: absolute; top: 80px; left: 15px; z-index: 1000;
                display: flex; flex-direction: column; gap: 10px; max-height: calc(100vh - 100px); overflow-y: auto;
            }
            .left-sidebar-container::-webkit-scrollbar { display: none; }

            /* 1. แผงคำนวณการยิงสนับสนุน (Ballistics CFF) */
            .fire-support-panel {
                background: rgba(10, 16, 13, 0.96); backdrop-filter: blur(14px);
                border: 1.5px solid #ff3838; border-radius: 14px;
                padding: 12px 16px; display: flex; flex-direction: column; gap: 6px;
                box-shadow: 0 12px 35px rgba(255,56,56,0.3); width: 310px; transition: 0.3s;
            }
            .fire-support-panel.collapsed { width: 180px; padding: 8px 12px; }
            .fire-support-panel.collapsed .fire-content { display: none; }
            .fire-title { font-size: 12px; font-weight: 700; color: #ff3838; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid rgba(255,56,56,0.4); padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
            .fire-row { display: flex; justify-content: space-between; font-size: 11.5px; font-family: 'Share Tech Mono', monospace; color: #e2e8e5; margin-top: 2px; }
            .fire-highlight { color: #00ffcc; font-weight: bold; }
            .btn-fire-action {
                background: linear-gradient(180deg, #ff3838 0%, #b71c1c 100%);
                border: 1px solid #ff3838; color: #fff; font-weight: bold; font-size: 11.5px;
                padding: 7px; border-radius: 6px; cursor: pointer; text-align: center; text-transform: uppercase; margin-top: 4px;
            }
            .cff-input-box {
                background: rgba(0,0,0,0.7); border: 1px solid rgba(212,175,55,0.4); color: #fff;
                padding: 4px 6px; font-size: 11.5px; border-radius: 4px; width: 100%; margin-top: 2px; font-family: 'Chakra Petch', sans-serif;
            }

            /* 2. แผงวอร์รูมวางแผน */
            .warroom-panel {
                background: rgba(10, 16, 13, 0.96); backdrop-filter: blur(14px);
                border: 1.5px solid rgba(212, 175, 55, 0.5); border-radius: 14px;
                padding: 12px 16px; display: flex; flex-direction: column; gap: 8px;
                box-shadow: 0 12px 35px rgba(0,0,0,0.85); width: 310px; transition: 0.3s;
            }
            .warroom-panel.collapsed { width: 180px; padding: 8px 12px; }
            .warroom-panel.collapsed .warroom-content { display: none; }
            .warroom-title { font-size: 12px; font-weight: 700; color: var(--gold-accent); text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid rgba(212,175,55,0.3); padding-bottom: 6px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
            .section-label { font-size: 11px; color: #8da196; font-weight: 600; margin-top: 4px; }
            .unit-selector-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; max-height: 140px; overflow-y: auto; padding-right: 2px; }
            .unit-btn {
                background: rgba(25, 38, 30, 0.9); border: 1.5px solid rgba(212, 175, 55, 0.4);
                border-radius: 8px; padding: 6px; font-size: 24px; text-align: center; cursor: pointer; transition: 0.2s;
            }
            .unit-btn:hover { border-color: var(--gold-accent); transform: scale(1.1); background: rgba(212,175,55,0.25); }
            .unit-btn.active { border-color: #00ffcc; background: rgba(0,255,204,0.3); box-shadow: 0 0 12px #00ffcc; }
            
            .color-palette { display: flex; gap: 6px; margin-top: 2px; }
            .color-dot { width: 22px; height: 22px; border-radius: 50%; cursor: pointer; border: 2px solid transparent; transition: 0.2s; }
            .color-dot.active { border-color: #fff; transform: scale(1.15); box-shadow: 0 0 10px rgba(255,255,255,0.6); }
            
            .draw-tools-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 4px; }
            .btn-draw-tool { background: rgba(25,38,30,0.9); border: 1px solid rgba(212,175,55,0.4); color: #cfd8dc; font-size: 11px; font-weight: bold; padding: 6px 4px; border-radius: 6px; cursor: pointer; text-align: center; }
            .btn-draw-tool.active { background: #d4af37; color: #000; border-color: #fff; }
            
            .warroom-actions { display: flex; gap: 6px; margin-top: 6px; border-top: 1px solid rgba(212,175,55,0.3); padding-top: 6px; }
            .btn-war { flex: 1; padding: 7px; font-size: 11px; font-weight: 700; border-radius: 6px; cursor: pointer; text-align: center; border: 1px solid; }
            .btn-clear-plan { background: rgba(229,57,53,0.25); border-color: #e53935; color: #ff6b6b; }
            .btn-mode { background: rgba(212,175,55,0.3); border-color: var(--gold-accent); color: var(--gold-accent); }

            /* 3. แผงสภาพอากาศทางทหาร */
            .weather-panel {
                background: rgba(10, 16, 13, 0.96); backdrop-filter: blur(14px);
                border: 1.5px solid rgba(0, 255, 204, 0.5); border-radius: 12px;
                padding: 10px 14px; width: 310px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); transition: 0.3s;
            }
            .weather-panel.collapsed { width: 180px; padding: 6px 10px; }
            .weather-panel.collapsed .weather-content { display: none; }
            .weather-title { font-size: 11.5px; font-weight: 700; color: #00ffcc; text-transform: uppercase; border-bottom: 1px solid rgba(0,255,204,0.3); padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
            .weather-val { font-family: 'Share Tech Mono', monospace; font-size: 12.5px; color: #e2e8e5; margin-top: 3px; }

            .huge-tactical-pin { font-size: 32px !important; text-align: center; filter: drop-shadow(0 0 4px #000) drop-shadow(0 2px 6px rgba(0,0,0,0.95)); cursor: pointer; line-height: 32px; border: 1.5px solid rgba(255,255,255,0.4); border-radius: 50%; background: rgba(10,15,12,0.6); padding: 2px; }

            .tactical-compass {
                position: absolute; bottom: 85px; right: 15px; z-index: 1000;
                background: rgba(10, 16, 13, 0.92); backdrop-filter: blur(10px);
                border: 1.5px solid var(--gold-accent); border-radius: 50%;
                width: 75px; height: 75px; display: flex; flex-direction: column; align-items: center; justify-content: center;
                box-shadow: 0 0 20px rgba(212,175,55,0.3); font-family: 'Share Tech Mono', monospace; color: #d4af37; font-weight: bold; font-size: 12px;
            }
            .compass-needle { font-size: 22px; transition: transform 0.2s; color: #ff3838; }
            .compass-toggle-btn {
                position: absolute; bottom: 170px; right: 15px; z-index: 1000;
                background: rgba(10,16,13,0.9); border: 1px solid var(--gold-accent); color: var(--gold-accent);
                padding: 4px 8px; font-size: 10px; border-radius: 6px; cursor: pointer; font-family: 'Chakra Petch', sans-serif;
            }

            #map-report-modal {
                display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); z-index: 20000;
                justify-content: center; align-items: center; padding: 15px;
            }
            #map-report-modal.show { display: flex; }
            .map-report-box {
                width: 100%; max-width: 480px; background: rgba(10, 15, 12, 0.96);
                border: 1.5px solid var(--gold-accent); border-radius: 16px; padding: 22px;
                box-shadow: 0 0 40px rgba(0,0,0,0.9); max-height: 90vh; overflow-y: auto;
            }

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

        <!-- ฟอร์มปักหมุดส่งรายงาน 5 หัวข้อ -->
        <div id="map-report-modal">
            <div class="map-report-box">
                <div style="font-size:16px; font-weight:bold; color:var(--gold-accent); margin-bottom:12px; border-bottom:1px solid #d4af37; padding-bottom:6px; display:flex; justify-content:space-between;">
                    <span>🚨 ส่งรายงานสถานการณ์ยุทธวิธี (SITREP)</span>
                    <span style="cursor:pointer; color:#ff6b6b;" onclick="closeMapReportModal()">✕</span>
                </div>
                <div class="form-group">
                    <label>🔑 รหัสผ่าน (Passcode - phantom2):</label>
                    <input type="password" id="m_passcode" placeholder="กรอกรหัสผ่าน">
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label>สถานการณ์:</label>
                        <input type="text" id="m_situation" placeholder="เช่น การปะทะ / ตรวจพบ">
                    </div>
                    <div class="form-group">
                        <label>สัญลักษณ์ยุทธวิธี:</label>
                        <select id="m_tactical_icon">
                            <option value="🎯 ตรวจพบเป้าหมาย">🎯 ตรวจพบเป้าหมาย</option>
                            <option value="⚔️ จุดปะทะ/ใช้อาวุธ">⚔️ จุดปะทะ</option>
                            <option value="🛡️ ฐานปฏิบัติการ/ที่มั่น">🛡️ ฐานที่มั่น</option>
                            <option value="⚠️ วัตถุต้องสงสัย/IED">⚠️ วัตถุต้องสงสัย</option>
                            <option value="🚁 จุดส่งกลับ/ลาน ฮ.">🚁 ลาน ฮ.</option>
                            <option value="⛺ จุดตรวจ/ค่ายพัก">⛺ จุดตรวจ</option>
                            <option value="💧 แหล่งน้ำ/เสบียง">💧 แหล่งเสบียง</option>
                            <option value="📡 ที่ตั้งสื่อสาร/เรดาร์">📡 สถานีสื่อสาร</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>พิกัดเป้าหมาย (Lat, Lon):</label>
                    <input type="text" id="m_coords" class="readonly-input" readonly>
                </div>
                <div class="form-group">
                    <label>เหตุการณ์:</label>
                    <textarea id="m_incident" rows="2" placeholder="รายละเอียดเหตุการณ์สิ่งที่ตรวจพบ"></textarea>
                </div>
                <div class="form-group">
                    <label>การปฏิบัติ:</label>
                    <textarea id="m_action" rows="2" placeholder="การวางกำลัง / การตอบโต้"></textarea>
                </div>
                <div class="form-group">
                    <label>📷 แนบภาพถ่าย (ถ้ามี):</label>
                    <input type="file" id="m_file_input" accept="image/*">
                </div>
                <button type="button" class="btn-action" onclick="submitMapReport()" style="margin-top:10px;">ส่งรายงานเข้าศูนย์ยุทธการ</button>
            </div>
        </div>

        <div class="header-bar">
            <h2>🗺️ PHANTOM COMBAT OPERATIONS</h2>
            <p id="total_reports">กำลังโหลดพิกัดรายงานยุทธวิธี...</p>
        </div>

        <div class="dashboard-search-container" id="dash_search_box" style="display: none;">
            <span style="font-size:16px; margin-right:6px;">🔍</span>
            <input type="text" id="dash_search_input" placeholder="ค้นหาชื่อสถานที่, ค่ายทหาร, พิกัด Lat,Lon หรือ MGRS..." onkeypress="if(event.key==='Enter') searchDashboardLocation()">
            <button type="button" onclick="searchDashboardLocation()">ค้นหา</button>
        </div>

        <!-- แผงควบคุมฝั่งซ้ายทั้งหมด (พับเก็บได้) -->
        <div class="left-sidebar-container" id="left_sidebar" style="display: none;">
            
            <!-- 1. แผงคำนวณการยิงสนับสนุน (Ballistics CFF) -->
            <div class="fire-support-panel" id="fire_panel">
                <div class="fire-title" onclick="toggleFirePanel()">
                    <span>💥 คำนวณการยิงสนับสนุน (CFF)</span>
                    <span id="fire_toggle_icon">▼ พับเก็บ</span>
                </div>
                <div class="fire-content">
                    <div style="font-size:11px; color:#a2b5aa; margin-top:4px;">เลือกอาวุธยิงสนับสนุน:</div>
                    <select id="fire_weapon_select" onchange="calculateBallistics()" class="cff-input-box" style="border-color:#ff3838;">
                        <option value="mortar_60">💣 ค. 60 มม. (ระยะ 70 - 3,500 ม.)</option>
                        <option value="mortar_81" selected>💣 ค. 81 มม. (ระยะ 100 - 5,600 ม.)</option>
                        <option value="mortar_120">💣 ค. 120 มม. (ระยะ 200 - 7,200 ม.)</option>
                        <option value="arty_105">💥 ปืนใหญ่ 105 มม. (ระยะ 11.5 กม.)</option>
                        <option value="arty_155">💥 ปืนใหญ่ 155 มม. (ระยะ 30 กม.)</option>
                    </select>

                    <div style="display:flex; gap:6px; margin-top:6px;">
                        <button type="button" class="btn-draw-tool" id="btn_pick_gun" onclick="startPickFirePoint('GUN')" style="flex:1; border-color:#00ffcc; color:#00ffcc;">📍 1. ปักที่ตั้งยิง</button>
                        <button type="button" class="btn-draw-tool" id="btn_pick_target" onclick="startPickFirePoint('TARGET')" style="flex:1; border-color:#ff3838; color:#ff3838;">❌ 2. ปักที่หมาย</button>
                    </div>

                    <div style="font-size:10.5px; color:#ff9800; margin-top:4px;">หรือกรอกพิกัดเป้าหมายเอง (Manual):</div>
                    <input type="text" id="manual_target_input" class="cff-input-box" placeholder="กรอก Lat,Lon หรือ MGRS" onchange="manualTargetCoords(this.value)">

                    <div class="fire-row" style="margin-top:6px; border-top:1px dashed rgba(255,56,56,0.3); padding-top:4px;"><span>พิกัดยิง (FOB):</span><span class="fire-highlight" id="f_gun_mgrs">N/A</span></div>
                    <div class="fire-row"><span>พิกัดที่หมาย:</span><span class="fire-highlight" id="f_target_mgrs">N/A</span></div>
                    <div class="fire-row"><span>ระยะยิงจริง:</span><span class="fire-highlight" id="f_dist">0 ม.</span></div>
                    <div class="fire-row"><span>มุมทิศ (Azimuth):</span><span class="fire-highlight" id="f_azimuth">0° (0 Mils)</span></div>
                    <div class="fire-row"><span>มุมสูง (QE):</span><span class="fire-highlight" id="f_qe">0 Mils</span></div>
                    <div class="fire-row"><span>เวลาตกกระทบ (TOF):</span><span class="fire-highlight" id="f_tof">~0 วินาที</span></div>
                    <div class="fire-row"><span>สถานะระยะยิง:</span><span id="f_status" style="color:#8da196;">รอระบุพิกัด</span></div>

                    <button type="button" class="btn-fire-action" onclick="sendFireSupportToLinePrompt()">🚀 ส่งคำสั่งยิงสนับสนุน (LINE)</button>
                </div>
            </div>

            <!-- 2. แผงวอร์รูมวางแผน -->
            <div class="warroom-panel" id="warroom_panel">
                <div class="warroom-title" onclick="toggleWarroomPanel()">
                    <span>🛡️ วอร์รูม & เขตการรบ</span>
                    <span id="warroom_toggle_icon">▼ พับเก็บ</span>
                </div>
                <div class="warroom-content">
                    <div class="section-label">📌 เลือกไอคอนหน่วยกำลังทหาร (ไม่ซ้ำ):</div>
                    <div class="unit-selector-grid">
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🪖', 'กองกำลังพล', this)" title="กองกำลังพล">🪖</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🚀', 'ปืนใหญ่/จรวด', this)" title="ปืนใหญ่">🚀</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🛑', 'จุดสกัด', this)" title="จุดสกัด">🛑</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '⚡', 'หน่วยจู่โจม', this)" title="หน่วยจู่โจม">⚡</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '✈️', 'เครื่องบินรบ', this)" title="เครื่องบินรบ">✈️</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🚙', 'รถหุ้มเกราะ', this)" title="รถหุ้มเกราะ">🚙</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🚒', 'รถพยาบาล', this)" title="รถพยาบาล">🚒</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '⚓', 'ฐานทัพเรือ', this)" title="ฐานทัพเรือ">⚓</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🧱', 'แนวป้องกัน', this)" title="แนวป้องกัน">🧱</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '⛽', 'คลังเชื้อเพลิง', this)" title="คลังเชื้อเพลิง">⛽</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '☣️', 'สารเคมี/ชีวะ', this)" title="สารเคมี">☣️</div>
                        <div class="unit-btn" onclick="selectWarTool('UNIT', '🏁', 'จุดหมายปลายทาง', this)" title="จุดหมาย">🏁</div>
                    </div>

                    <div class="section-label" style="margin-top:6px;">🎨 เลือกสีเขตแนวรบ:</div>
                    <div class="color-palette">
                        <div class="color-dot active" style="background:#ff3838;" onclick="setDrawColor('#ff3838', this)"></div>
                        <div class="color-dot" style="background:#2196f3;" onclick="setDrawColor('#2196f3', this)"></div>
                        <div class="color-dot" style="background:#00ffcc;" onclick="setDrawColor('#00ffcc', this)"></div>
                        <div class="color-dot" style="background:#d4af37;" onclick="setDrawColor('#d4af37', this)"></div>
                        <div class="color-dot" style="background:#ff9800;" onclick="setDrawColor('#ff9800', this)"></div>
                    </div>

                    <div class="section-label" style="margin-top:6px;">📐 เครื่องมือวาด (ปรับขนาดได้):</div>
                    <div class="draw-tools-row">
                        <button type="button" class="btn-draw-tool" onclick="selectWarTool('DRAW', 'LINE', 'เส้นทาง', this)">📏 เส้นทาง</button>
                        <button type="button" class="btn-draw-tool" onclick="selectWarTool('DRAW', 'CIRCLE', 'วงกลม', this)">⭕ วงกลม</button>
                        <button type="button" class="btn-draw-tool" onclick="selectWarTool('DRAW', 'RECT', 'สี่เหลี่ยม', this)">⬛ สี่เหลี่ยม</button>
                    </div>

                    <div class="warroom-actions">
                        <button type="button" class="btn-war btn-mode" onclick="toggleAddMode()" id="mode_toggle_btn">โหมดวาง: เปิด</button>
                        <button type="button" class="btn-war btn-clear-plan" onclick="clearWarUnits()">🗑️ ล้างกระดาน</button>
                    </div>
                </div>
            </div>

            <!-- 3. แผงสภาพอากาศทางทหาร -->
            <div class="weather-panel" id="weather_panel">
                <div class="weather-title" onclick="toggleWeatherPanel()">
                    <span>⛅ สภาพอากาศ & โอกาสฝนตก</span>
                    <span id="weather_toggle_icon">▼ พับเก็บ</span>
                </div>
                <div class="weather-content">
                    <div class="weather-val" id="w_temp">🌡️ อุณหภูมิ: กำลังโหลด...</div>
                    <div class="weather-val" id="w_rain">🌧️ โอกาสฝนตก: กำลังวิเคราะห์...</div>
                    <div class="weather-val" id="w_wind">💨 แรงลม: กำลังโหลด...</div>
                    <div class="weather-val" id="w_impact" style="color:#00ffcc; font-size:11px; margin-top:4px;">⚡ พร้อมประเมินผลกระทบยุทธวิธี</div>
                </div>
            </div>

        </div>

        <button type="button" class="compass-toggle-btn" id="compass_toggle_btn" style="display: none;" onclick="toggleCompass()">🧭 ซ่อนเข็มทิศ</button>
        
        <div class="tactical-compass" id="tactical_compass" style="display: none;">
            <div class="compass-needle" id="compass_needle">⬆️</div>
            <span id="compass_deg">0° N</span>
        </div>

        <div class="map-switch-top">
            <select onchange="changeDashboardLayer(this.value)">
                <option value="google_sat">🌐 Google Maps (Satellite)</option>
                <option value="esri_sat">🛰️ ESRI World Imagery (Mil)</option>
                <option value="google_road">🗺️ Google Maps (Road)</option>
                <option value="opentopo">⛰️ OpenTopoMap (Terrain)</option>
            </select>
        </div>

        <!-- แถบกรองข้อมูลด้านล่าง พร้อมตัวนับจำนวนและกดซูมพุ่งไปยังจุดปักหมุด -->
        <div class="tactical-filter-bar" id="filter_bar" style="display: none;">
            <div class="filter-chip active" onclick="applyQuickFilter('ALL', this)">
                <span>🌐 ทั้งหมด</span>
                <span class="filter-count" id="count_ALL">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('🎯', this)">
                <span>🎯 เป้าหมาย</span>
                <span class="filter-count" id="count_🎯">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('⚔️', this)">
                <span>⚔️ จุดปะทะ</span>
                <span class="filter-count" id="count_⚔️">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('🛡️', this)">
                <span>🛡️ ฐานที่มั่น</span>
                <span class="filter-count" id="count_🛡️">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('⚠️', this)">
                <span>⚠️ วัตถุต้องสงสัย</span>
                <span class="filter-count" id="count_⚠️">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('🚁', this)">
                <span>🚁 ลาน ฮ.</span>
                <span class="filter-count" id="count_🚁">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('⛺', this)">
                <span>⛺ จุดตรวจ</span>
                <span class="filter-count" id="count_⛺">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('💧', this)">
                <span>💧 แหล่งเสบียง</span>
                <span class="filter-count" id="count_💧">0</span>
            </div>
            <div class="filter-chip" onclick="applyQuickFilter('📡', this)">
                <span>📡 สถานีสื่อสาร</span>
                <span class="filter-count" id="count_📡">0</span>
            </div>
        </div>

        <div id="dashboard-map"></div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/mgrs@1.0.0/dist/mgrs.min.js"></script>
        <script>
            let currentAdminKey = "";
            let currentReportsData = [];
            let activeFilter = "ALL";
            let mapLayersGroup = L.layerGroup();
            let warUnitsLayer = L.layerGroup();
            let fireSupportLayer = L.layerGroup();
            let searchMarker = null;

            let currentToolType = 'UNIT';
            let selectedWarEmoji = '🪖';
            let selectedToolName = 'กองกำลังพล';
            let activeDrawShape = 'LINE';
            let activeColor = '#ff3838';
            let isWarModeActive = false;
            let drawingPoints = [];
            let selectedMapLatLng = null;
            let isCompassVisible = true;

            // ตัวแปรระบบยิงสนับสนุน CFF
            let pickFireMode = null;
            let gunLatLng = null;
            let targetLatLng = null;
            let currentBallisticsResult = null;
            let cffTargetName = "เป้าหมายข้าศึก";
            let cffTargetImage = null;

            const weaponRanges = {
                mortar_60: { name: "ค. 60 มม.", min: 70, max: 3500, lethalRadius: 20, speed: 170 },
                mortar_81: { name: "ค. 81 มม.", min: 100, max: 5600, lethalRadius: 35, speed: 240 },
                mortar_120: { name: "ค. 120 มม.", min: 200, max: 7200, lethalRadius: 60, speed: 310 },
                arty_105: { name: "ปืนใหญ่ 105 มม.", min: 1000, max: 11500, lethalRadius: 50, speed: 450 },
                arty_155: { name: "ปืนใหญ่ 155 มม.", min: 2000, max: 30000, lethalRadius: 80, speed: 680 }
            };

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
            warUnitsLayer.addTo(map);
            fireSupportLayer.addTo(map);

            function toggleFirePanel() {
                const panel = document.getElementById('fire_panel');
                const icon = document.getElementById('fire_toggle_icon');
                panel.classList.toggle('collapsed');
                icon.innerText = panel.classList.contains('collapsed') ? "▶ ขยาย" : "▼ พับเก็บ";
            }
            function toggleWarroomPanel() {
                const panel = document.getElementById('warroom_panel');
                const icon = document.getElementById('warroom_toggle_icon');
                panel.classList.toggle('collapsed');
                icon.innerText = panel.classList.contains('collapsed') ? "▶ ขยาย" : "▼ พับเก็บ";
            }
            function toggleWeatherPanel() {
                const panel = document.getElementById('weather_panel');
                const icon = document.getElementById('weather_toggle_icon');
                panel.classList.toggle('collapsed');
                icon.innerText = panel.classList.contains('collapsed') ? "▶ ขยาย" : "▼ พับเก็บ";
            }
            function toggleCompass() {
                isCompassVisible = !isCompassVisible;
                document.getElementById('tactical_compass').style.display = isCompassVisible ? 'flex' : 'none';
                document.getElementById('compass_toggle_btn').innerText = isCompassVisible ? "🧭 ซ่อนเข็มทิศ" : "🧭 แสดงเข็มทิศ";
            }

            // --- ฟังก์ชันระบบคำนวณการยิงสนับสนุน CFF ---
            function startPickFirePoint(type) {
                pickFireMode = type;
                isWarModeActive = false;
                document.getElementById('mode_toggle_btn').innerText = "โหมดวาง: ปิด";
                document.getElementById('mode_toggle_btn').style.background = "rgba(212,175,55,0.1)";

                if (type === 'GUN') {
                    document.getElementById('btn_pick_gun').style.background = '#00ffcc';
                    document.getElementById('btn_pick_gun').style.color = '#000';
                    document.getElementById('btn_pick_target').style.background = '';
                    document.getElementById('btn_pick_target').style.color = '#ff3838';
                } else {
                    document.getElementById('btn_pick_target').style.background = '#ff3838';
                    document.getElementById('btn_pick_target').style.color = '#fff';
                    document.getElementById('btn_pick_gun').style.background = '';
                    document.getElementById('btn_pick_gun').style.color = '#00ffcc';
                }
            }

            function manualTargetCoords(val) {
                val = val.trim();
                if (!val) return;
                const latLonRegex = /^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)[,\s]+[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$/;
                if (latLonRegex.test(val)) {
                    const p = val.split(/[\s,]+/);
                    targetLatLng = { lat: parseFloat(p[0]), lng: parseFloat(p[1]) };
                    calculateBallistics();
                    return;
                }
                try {
                    const cleanMGRS = val.replace(/\s+/g, '').toUpperCase();
                    if (typeof mgrs !== 'undefined' && mgrs.toPoint) {
                        const pt = mgrs.toPoint(cleanMGRS);
                        if (pt && pt.length === 2) {
                            targetLatLng = { lat: pt[1], lng: pt[0] };
                            calculateBallistics();
                            return;
                        }
                    }
                } catch(e) {}
                alert('⚠️ รูปแบบพิกัดไม่ถูกต้อง');
            }

            function calculateBearing(lat1, lon1, lat2, lon2) {
                const toRad = deg => deg * Math.PI / 180;
                const toDeg = rad => rad * 180 / Math.PI;
                const dLon = toRad(lon2 - lon1);
                const y = Math.sin(dLon) * Math.cos(toRad(lat2));
                const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
                let brng = toDeg(Math.atan2(y, x));
                return (brng + 360) % 360;
            }

            function calculateBallistics() {
                fireSupportLayer.clearLayers();

                if (gunLatLng) {
                    const gunMGRS = convertToMGRS(gunLatLng.lat, gunLatLng.lng);
                    document.getElementById('f_gun_mgrs').innerText = gunMGRS;
                    const gMarker = L.marker([gunLatLng.lat, gunLatLng.lng], {
                        icon: L.divIcon({ className: 'huge-tactical-pin', html: '📍', iconSize: [32, 32], iconAnchor: [16, 16] }),
                        draggable: true
                    }).addTo(fireSupportLayer);

                    gMarker.on('drag', function(ev) {
                        gunLatLng = ev.target.getLatLng();
                        calculateBallistics();
                    });

                    gMarker.bindPopup(`
                        <div style="text-align:center;">
                            <b>ที่ตั้งยิง (FOB):</b><br>${gunMGRS}<br>
                            <span style="font-size:10px; color:#7ee0ad;">(คลิกลากย้ายตำแหน่งได้)</span><br>
                            <button onclick="removeGunPoint()" style="margin-top:4px; background:#e53935; color:#fff; border:none; padding:3px 8px; border-radius:4px; cursor:pointer;">🗑️ ลบที่ตั้งยิง</button>
                        </div>
                    `);
                } else { document.getElementById('f_gun_mgrs').innerText = 'N/A'; }

                if (targetLatLng) {
                    const targetMGRS = convertToMGRS(targetLatLng.lat, targetLatLng.lng);
                    document.getElementById('f_target_mgrs').innerText = targetMGRS;
                    const tMarker = L.marker([targetLatLng.lat, targetLatLng.lng], {
                        icon: L.divIcon({ className: 'huge-tactical-pin', html: '❌', iconSize: [32, 32], iconAnchor: [16, 16] }),
                        draggable: true
                    }).addTo(fireSupportLayer);

                    tMarker.on('drag', function(ev) {
                        targetLatLng = ev.target.getLatLng();
                        calculateBallistics();
                    });

                    const pContent = `
                        <div style="min-width:220px;" class="sitrep-box">
                            <div style="font-size:14px; font-weight:bold; color:#ff3838; margin-bottom:6px; border-bottom:1px solid #ff3838; padding-bottom:4px;">❌ ที่หมายยิงสนับสนุน</div>
                            <div id="cff_t_view">
                                <b>ชื่อที่หมาย:</b> <span id="cff_t_name_disp">${cffTargetName}</span><br>
                                <b>พิกัด MGRS:</b> <span style="color:#00ffcc">${targetMGRS}</span><br>
                                <span style="font-size:10px; color:#7ee0ad;">(คลิกลากย้ายตำแหน่งเป้าหมายได้)</span>
                                <img id="cff_t_img_disp" src="${cffTargetImage || ''}" style="display:${cffTargetImage ? 'block' : 'none'}; width:100%; border-radius:6px; margin-top:6px; border:1px solid #ff3838;">
                                <div class="admin-tools">
                                    <button class="btn-admin-act btn-edit" onclick="editCffTarget()">✏️ แก้ไขชื่อ/รูป</button>
                                    <button class="btn-admin-act btn-del" onclick="removeTargetPoint()">🗑️ ลบที่หมาย</button>
                                </div>
                            </div>
                            <div id="cff_t_edit" style="display:none;">
                                ชื่อเป้าหมาย: <input type="text" id="cff_t_name_input" class="edit-box-input" value="${cffTargetName}"><br>
                                อัปโหลดรูปเป้าหมาย: <input type="file" id="cff_t_img_input" class="edit-box-input" accept="image/*"><br>
                                <div class="admin-tools">
                                    <button class="btn-admin-act btn-save" onclick="saveCffTarget()">💾 บันทึก</button>
                                    <button class="btn-admin-act btn-cancel" onclick="cancelCffTarget()">ยกเลิก</button>
                                </div>
                            </div>
                        </div>
                    `;
                    tMarker.bindPopup(pContent);
                } else { document.getElementById('f_target_mgrs').innerText = 'N/A'; }

                if (!gunLatLng || !targetLatLng) {
                    document.getElementById('f_dist').innerText = "0 ม.";
                    document.getElementById('f_azimuth').innerText = "0° (0 Mils)";
                    document.getElementById('f_qe').innerText = "0 Mils";
                    document.getElementById('f_tof').innerText = "~0 วินาที";
                    document.getElementById('f_status').innerText = "รอระบุจุดยิงและเป้าหมาย";
                    currentBallisticsResult = null;
                    return;
                }

                const wKey = document.getElementById('fire_weapon_select').value;
                const weapon = weaponRanges[wKey];
                const p1 = L.latLng(gunLatLng.lat, gunLatLng.lng);
                const p2 = L.latLng(targetLatLng.lat, targetLatLng.lng);

                const distanceMeters = p1.distanceTo(p2);
                const azimuthDeg = calculateBearing(gunLatLng.lat, gunLatLng.lng, targetLatLng.lat, targetLatLng.lng);
                const azimuthMils = (azimuthDeg / 360) * 6400;
                
                let ratio = distanceMeters / weapon.max;
                if (ratio > 1.0) ratio = 1.0;
                const qeDeg = (Math.asin(ratio) * (180 / Math.PI)) / 2;
                const qeMils = (qeDeg / 360) * 6400;

                const tofSeconds = Math.round(distanceMeters / weapon.speed) + 2;

                const gunMGRS = convertToMGRS(gunLatLng.lat, gunLatLng.lng);
                const targetMGRS = convertToMGRS(targetLatLng.lat, targetLatLng.lng);

                document.getElementById('f_dist').innerText = `${distanceMeters.toFixed(0)} ม. (${(distanceMeters/1000).toFixed(2)} กม.)`;
                document.getElementById('f_azimuth').innerText = `${azimuthDeg.toFixed(1)}° (${azimuthMils.toFixed(0)} Mils)`;
                document.getElementById('f_qe').innerText = `${qeMils.toFixed(0)} Mils (${qeDeg.toFixed(1)}°)`;
                document.getElementById('f_tof').innerText = `~${tofSeconds} วินาที`;

                const statusEl = document.getElementById('f_status');
                if (distanceMeters < weapon.min) {
                    statusEl.innerText = `⚠️ ใกล้เกินระยะต่ำสุด (${weapon.min} ม.)`;
                    statusEl.style.color = '#ff3838';
                } else if (distanceMeters > weapon.max) {
                    statusEl.innerText = `⚠️ เกินระยะสูงสุด (${(weapon.max/1000).toFixed(1)} กม.)`;
                    statusEl.style.color = '#ff3838';
                } else {
                    statusEl.innerText = `✅ อยู่ในระยะหวังผล (IN-RANGE)`;
                    statusEl.style.color = '#00ffcc';
                }

                L.polyline([[gunLatLng.lat, gunLatLng.lng], [targetLatLng.lat, targetLatLng.lng]], {
                    color: '#ff3838', weight: 4, dashArray: '6, 8'
                }).addTo(fireSupportLayer);

                L.circle([targetLatLng.lat, targetLatLng.lng], {
                    radius: weapon.lethalRadius, color: '#ff3838', fillColor: '#ff3838', fillOpacity: 0.35, weight: 2
                }).addTo(fireSupportLayer);

                currentBallisticsResult = {
                    weapon_type: weapon.name,
                    gun_coords: `${gunLatLng.lat.toFixed(6)}, ${gunLatLng.lng.toFixed(6)}`,
                    gun_mgrs: gunMGRS,
                    target_coords: `${targetLatLng.lat.toFixed(6)}, ${targetLatLng.lng.toFixed(6)}`,
                    target_mgrs: targetMGRS,
                    distance_meters: distanceMeters,
                    azimuth_deg: azimuthDeg,
                    azimuth_mils: azimuthMils,
                    qe_mils: qeMils,
                    tof_seconds: tofSeconds
                };
            }

            function editCffTarget() {
                document.getElementById('cff_t_view').style.display = 'none';
                document.getElementById('cff_t_edit').style.display = 'block';
            }
            function cancelCffTarget() {
                document.getElementById('cff_t_view').style.display = 'block';
                document.getElementById('cff_t_edit').style.display = 'none';
            }
            function saveCffTarget() {
                cffTargetName = document.getElementById('cff_t_name_input').value || "เป้าหมายข้าศึก";
                const fileInput = document.getElementById('cff_t_img_input');
                if (fileInput.files && fileInput.files[0]) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        cffTargetImage = e.target.result;
                        calculateBallistics();
                    };
                    reader.readAsDataURL(fileInput.files[0]);
                } else {
                    calculateBallistics();
                }
            }

            function removeGunPoint() { gunLatLng = null; calculateBallistics(); }
            function removeTargetPoint() { targetLatLng = null; calculateBallistics(); }

            async function sendFireSupportToLinePrompt() {
                if (!currentBallisticsResult) {
                    alert('⚠️ กรุณาระบุที่ตั้งยิงและเป้าหมายบนแผนที่ก่อน');
                    return;
                }
                const pass = prompt("🔑 ยืนยันคำสั่งยิงสนับสนุน: กรุณากรอกรหัสความปลอดภัย (wisarut)");
                if (pass === null) return;
                if (pass !== "wisarut") { alert('❌ รหัสผ่านไม่ถูกต้อง! ปฏิเสธคำขอยิง'); return; }

                try {
                    const payload = {
                        ...currentBallisticsResult,
                        passcode: pass,
                        target_name: cffTargetName,
                        image_base64: cffTargetImage
                    };
                    const res = await fetch('/api/send-fire-support', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
                    });
                    if (res.ok) alert('🚀 ส่งคำสั่งยิงสนับสนุน (CALL FOR FIRE) เข้ากลุ่ม LINE สำเร็จ!');
                    else alert('❌ ส่งคำขอยิงล้มเหลว');
                } catch(e) { alert('⚠️ เชื่อมต่อล้มเหลว'); }
            }

            function selectWarTool(type, val1, val2, element) {
                currentToolType = type;
                pickFireMode = null;
                document.getElementById('btn_pick_gun').style.background = '';
                document.getElementById('btn_pick_gun').style.color = '#00ffcc';
                document.getElementById('btn_pick_target').style.background = '';
                document.getElementById('btn_pick_target').style.color = '#ff3838';

                document.querySelectorAll('.unit-btn, .btn-draw-tool').forEach(b => b.classList.remove('active'));
                element.classList.add('active');
                isWarModeActive = true;
                document.getElementById('mode_toggle_btn').innerText = "โหมดวาง: เปิด";
                document.getElementById('mode_toggle_btn').style.background = "rgba(212,175,55,0.3)";

                if (type === 'UNIT') { selectedWarEmoji = val1; selectedToolName = val2; } 
                else if (type === 'DRAW') { activeDrawShape = val1; selectedToolName = val2; drawingPoints = []; }
            }

            function setDrawColor(color, element) {
                document.querySelectorAll('.color-dot').forEach(d => d.classList.remove('active'));
                element.classList.add('active'); activeColor = color;
            }

            function toggleAddMode() {
                isWarModeActive = !isWarModeActive;
                pickFireMode = null;
                const btn = document.getElementById('mode_toggle_btn');
                btn.innerText = isWarModeActive ? "โหมดวาง: เปิด" : "โหมดวาง: ปิด";
                btn.style.background = isWarModeActive ? "rgba(212,175,55,0.3)" : "rgba(212,175,55,0.1)";
            }

            function deleteWarLayer(id) {
                if (warUnitsLayer.hasLayer(id)) warUnitsLayer.removeLayer(id);
            }

            // ระบบคลิกบนแผนที่
            map.on('click', function(e) {
                const lat = e.latlng.lat; 
                const lng = e.latlng.lng;

                if (pickFireMode === 'GUN') {
                    gunLatLng = { lat, lng }; 
                    pickFireMode = null;
                    document.getElementById('btn_pick_gun').style.background = '';
                    document.getElementById('btn_pick_gun').style.color = '#00ffcc';
                    calculateBallistics();
                    return;
                } else if (pickFireMode === 'TARGET') {
                    targetLatLng = { lat, lng }; 
                    pickFireMode = null;
                    document.getElementById('btn_pick_target').style.background = '';
                    document.getElementById('btn_pick_target').style.color = '#ff3838';
                    calculateBallistics();
                    return;
                }

                if (!isWarModeActive) return;

                if (currentToolType === 'UNIT') {
                    const marker = L.marker([lat, lng], {
                        icon: L.divIcon({ className: 'huge-tactical-pin', html: selectedWarEmoji, iconSize: [32, 32], iconAnchor: [16, 16] }), draggable: true
                    }).addTo(warUnitsLayer);
                    const id = marker._leaflet_id;
                    marker.bindPopup(`
                        <div style="text-align:center;" class="sitrep-box">
                            <b style="color:#d4af37; font-size:14px;">${selectedWarEmoji} ${selectedToolName}</b><br>
                            <span style="font-size:11.5px; color:#00ffcc;">พิกัด: ${lat.toFixed(5)}, ${lng.toFixed(5)}</span><br>
                            <button onclick="deleteWarLayer(${id})" style="margin-top:6px; background:#e53935; color:#fff; border:none; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px;">🗑️ ลบหน่วยนี้</button>
                            <button onclick="openMapReportAt(${lat}, ${lng})" style="margin-top:4px; display:block; width:100%; background:#d4af37; color:#000; font-weight:bold; border:none; padding:4px; border-radius:4px; cursor:pointer; font-size:11px;">🚨 ส่งรายงาน 5 หัวข้อจุดนี้</button>
                        </div>
                    `);
                } else if (currentToolType === 'DRAW') {
                    drawingPoints.push([lat, lng]);
                    if (activeDrawShape === 'LINE' && drawingPoints.length === 2) {
                        const line = L.polyline(drawingPoints, { color: activeColor, weight: 4, dashArray: '6, 6' }).addTo(warUnitsLayer);
                        const id = line._leaflet_id;
                        line.bindPopup(`<b>เส้นทาง/แนวรบ</b><br><button onclick="deleteWarLayer(${id})" style="background:#e53935; color:#fff; border:none; padding:3px 6px; border-radius:3px; cursor:pointer; font-size:11px;">🗑️ ลบเส้นนี้</button>`);
                        drawingPoints = [];
                    } else if (activeDrawShape === 'CIRCLE' && drawingPoints.length === 1) {
                        const circle = L.circle(drawingPoints[0], { radius: 1000, color: activeColor, fillColor: activeColor, fillOpacity: 0.2, weight: 2, draggable: true }).addTo(warUnitsLayer);
                        const edgeLatLng = L.latLng(drawingPoints[0][0], drawingPoints[0][1] + 0.01);
                        const radiusHandle = L.marker(edgeLatLng, { draggable: true, icon: L.divIcon({ className: 'custom-tactical-pin', html: '⭕', iconSize: [16, 16], iconAnchor: [8, 8] }) }).addTo(warUnitsLayer);
                        const id = circle._leaflet_id;
                        const handleId = radiusHandle._leaflet_id;
                        radiusHandle.on('drag', function(ev) { circle.setRadius(circle.getLatLng().distanceTo(ev.latlng)); });
                        circle.bindPopup(`<b>เขตวงกลมรบ (ลาก ⭕ ปรับขนาดได้)</b><br><button onclick="deleteWarLayer(${id}); deleteWarLayer(${handleId});" style="background:#e53935; color:#fff; border:none; padding:3px 6px; border-radius:3px; cursor:pointer; font-size:11px;">🗑️ ลบวงกลมนี้</button>`);
                        drawingPoints = [];
                    } else if (activeDrawShape === 'RECT' && drawingPoints.length === 2) {
                        const rect = L.rectangle([drawingPoints[0], drawingPoints[1]], { color: activeColor, fillColor: activeColor, fillOpacity: 0.15, weight: 2 }).addTo(warUnitsLayer);
                        const id = rect._leaflet_id;
                        rect.bindPopup(`<b>เขตพื้นที่ปิดล้อม</b><br><button onclick="deleteWarLayer(${id})" style="background:#e53935; color:#fff; border:none; padding:3px 6px; border-radius:3px; cursor:pointer; font-size:11px;">🗑️ ลบเขตนี้</button>`);
                        drawingPoints = [];
                    }
                }
            });

            function clearWarUnits() {
                warUnitsLayer.clearLayers();
                drawingPoints = [];
                alert('✅ ล้างแผนผังทั้งหมดสำเร็จ');
            }

            function openMapReportAt(lat, lng) {
                selectedMapLatLng = { lat, lng };
                document.getElementById('m_coords').value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
                document.getElementById('map-report-modal').classList.add('show');
            }
            function closeMapReportModal() { document.getElementById('map-report-modal').classList.remove('show'); }

            async function submitMapReport() {
                const pass = document.getElementById('m_passcode').value;
                const sit = document.getElementById('m_situation').value;
                const inc = document.getElementById('m_incident').value;
                const act = document.getElementById('m_action').value;
                const icon = document.getElementById('m_tactical_icon').value;
                if (!pass || !sit) { alert('กรุณากรอกรหัสผ่านและสถานการณ์'); return; }
                
                const fileInput = document.getElementById('m_file_input');
                if (fileInput.files[0]) {
                    const reader = new FileReader();
                    reader.onload = async function(e) { await sendReportAPI(pass, sit, inc, act, icon, [e.target.result]); };
                    reader.readAsDataURL(fileInput.files[0]);
                } else { await sendReportAPI(pass, sit, inc, act, icon, []); }
            }

            async function sendReportAPI(pass, sit, inc, act, icon, imgs) {
                try {
                    const res = await fetch('/api/submit-report', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ passcode: pass, situation: sit, incident: inc, action: act, latitude: selectedMapLatLng.lat, longitude: selectedMapLatLng.lng, radius_meters: 0, mgrs: convertToMGRS(selectedMapLatLng.lat, selectedMapLatLng.lng), tactical_icon: icon, images: imgs })
                    });
                    if (res.ok) { alert('✅ ส่งรายงานยุทธวิธีสำเร็จ!'); closeMapReportModal(); verifyAdminKey(); }
                    else { alert('❌ รหัสผ่านไม่ถูกต้อง (ใช้ phantom2)'); }
                } catch(e) { alert('เกิดข้อผิดพลาด'); }
            }

            async function fetchTacticalWeather(lat, lon) {
                try {
                    const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&hourly=precipitation_probability`);
                    const data = await res.json();
                    if (data && data.current_weather) {
                        const cw = data.current_weather;
                        document.getElementById('w_temp').innerText = `🌡️ อุณหภูมิ: ${cw.temperature} °C`;
                        document.getElementById('w_wind').innerText = `💨 แรงลม: ${cw.windspeed} กม./ชม. (ทิศ ${cw.winddirection}°)`;
                        
                        let rainChance = "ต่ำ (< 10%)";
                        if (data.hourly && data.hourly.precipitation_probability) {
                            rainChance = data.hourly.precipitation_probability[0] + " %";
                        }
                        document.getElementById('w_rain').innerText = `🌧️ โอกาสฝนตก: ${rainChance}`;

                        let impact = "⚡ สภาพอากาศเหมาะสมสำหรับปฏิบัติการ";
                        if (parseInt(rainChance) > 50) impact = "⚠️ ฝนตกหนัก! ทัศนวิสัยต่ำ การเคลื่อนพลลำบาก";
                        else if (cw.windspeed > 35) impact = "⚠️ ลมแรงจัด! ระวังการใช้อากาศยานและปืนใหญ่";
                        document.getElementById('w_impact').innerText = impact;
                    }
                } catch(e) {}
            }

            map.on('move', function() {
                const c = map.getCenter();
                fetchTacticalWeather(c.lat, c.lng);
            });
            setTimeout(() => { const c = map.getCenter(); fetchTacticalWeather(c.lat, c.lng); }, 1000);

            function changeDashboardLayer(k) {
                if (layers[k]) { map.removeLayer(activeLayer); activeLayer = layers[k]; activeLayer.addTo(map); }
            }

            function openLightbox(url) { document.getElementById('lightbox-img').src = url; document.getElementById('photo-lightbox').style.display = 'flex'; }
            function closeLightbox() { document.getElementById('photo-lightbox').style.display = 'none'; }

            async function verifyAdminKey() {
                const key = document.getElementById('admin_key_input').value.trim();
                if (!key) { alert('กรุณากรอกรหัสผ่าน'); return; }
                try {
                    const res = await fetch(`/api/get-all-reports?passcode=${encodeURIComponent(key)}`);
                    if (res.status === 403 || res.status === 401) { alert('รหัสผ่านไม่ถูกต้อง'); return; }
                    const data = await res.json();
                    currentAdminKey = key;
                    document.getElementById('auth-gate').style.display = 'none';
                    document.getElementById('dash_search_box').style.display = 'flex';
                    document.getElementById('left_sidebar').style.display = 'flex';
                    document.getElementById('compass_toggle_btn').style.display = 'block';
                    document.getElementById('tactical_compass').style.display = 'flex';
                    document.getElementById('filter_bar').style.display = 'flex';
                    map.invalidateSize();
                    currentReportsData = data;
                    updateFilterCounts(data);
                    renderMapData(data);
                } catch(e) { alert('เกิดข้อผิดพลาด'); }
            }

            async function searchDashboardLocation() {
                const q = document.getElementById('dash_search_input').value.trim();
                if (!q) return;
                if (searchMarker) map.removeLayer(searchMarker);

                const latLonRegex = /^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?)[,\s]+[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$/;
                if (latLonRegex.test(q)) {
                    const p = q.split(/[\s,]+/);
                    const lat = parseFloat(p[0]), lon = parseFloat(p[1]);
                    if (!isNaN(lat) && !isNaN(lon)) {
                        map.flyTo([lat, lon], 17);
                        searchMarker = L.marker([lat, lon]).addTo(map).bindPopup(`📍 พิกัด: ${lat.toFixed(6)}, ${lon.toFixed(6)}`).openPopup();
                        return;
                    }
                }

                try {
                    const cleanMGRS = q.replace(/\s+/g, '').toUpperCase();
                    if (typeof mgrs !== 'undefined' && mgrs.toPoint) {
                        const pt = mgrs.toPoint(cleanMGRS);
                        if (pt && pt.length === 2) {
                            map.flyTo([pt[1], pt[0]], 17);
                            searchMarker = L.marker([pt[1], pt[0]]).addTo(map).bindPopup(`📍 MGRS: ${cleanMGRS}`).openPopup();
                            return;
                        }
                    }
                } catch(e) {}

                try {
                    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&countrycodes=th`);
                    const data = await res.json();
                    if (data.length > 0) {
                        const lat = parseFloat(data[0].lat), lon = parseFloat(data[0].lon);
                        map.flyTo([lat, lon], 15);
                        searchMarker = L.marker([lat, lon]).addTo(map).bindPopup(`📍 ${data[0].display_name}`).openPopup();
                    } else { alert('ไม่พบสถานที่ดังกล่าว'); }
                } catch(e) { alert('ค้นหาล้มเหลว'); }
            }

            function updateFilterCounts(data) {
                const counts = { 'ALL': data.length, '🎯': 0, '⚔️': 0, '🛡️': 0, '⚠️': 0, '🚁': 0, '⛺': 0, '💧': 0, '📡': 0 };
                data.forEach(item => {
                    const match = (item.detail || "").match(/สัญลักษณ์ยุทธวิธี:\s*(\S+)/);
                    if (match && counts[match[1]] !== undefined) counts[match[1]]++;
                });
                for (let k in counts) {
                    const el = document.getElementById(`count_${k}`);
                    if (el) el.innerText = counts[k];
                }
            }

            function applyQuickFilter(emoji, chip) {
                activeFilter = emoji;
                document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                const filtered = emoji === 'ALL' ? currentReportsData : currentReportsData.filter(i => (i.detail || "").includes(emoji));
                renderMapData(filtered, true);
            }

            function formatCleanRedDetail(raw) {
                if (!raw) return "";
                return raw.replace(/^[0-9]+\.\s*/gm, '')
                    .replace(/(เวลา:|เวลาบันทึก:|สัญลักษณ์ยุทธวิธี:|รัศมีอันตราย:|สถานการณ์:|เหตุการณ์:|การปฏิบัติ:|พิกัด MGRS:|พิกัด GPS:|แผนที่ Google:|จำนวนภาพถ่าย:)/g, '<span class="sitrep-label-red">$1</span>');
            }

            function extractField(detail, fieldName) {
                return detail.match(new RegExp(`(?:[0-9]+\\.\\s*)?${fieldName}:\\s*(.*)`))?.[1] || "";
            }

            function renderMapData(data, autoZoom = false) {
                mapLayersGroup.clearLayers();
                if (data.length > 0) {
                    document.getElementById('total_reports').innerText = `แสดงรายงาน: ${data.length} จุด`;
                    const group = [];
                    data.forEach(item => {
                        if (item.latitude && item.longitude) {
                            const match = (item.detail || "").match(/สัญลักษณ์ยุทธวิธี:\s*(\S+)/);
                            const emoji = match ? match[1] : "🎯";
                            const marker = L.marker([item.latitude, item.longitude], { icon: L.divIcon({ className: 'huge-tactical-pin', html: emoji, iconSize: [32, 32], iconAnchor: [16, 16] }) }).addTo(mapLayersGroup);
                            
                            let gallery = "";
                            if (item.image_url) {
                                gallery = `<div class="popup-gallery">${item.image_url.split(",").map(u => `<img src="${u.trim()}" class="popup-thumb" onclick="openLightbox('${u.trim()}')">`).join("")}</div>`;
                            }

                            marker.bindPopup(`
                                <div style="min-width: 250px;" class="sitrep-box">
                                    <div style="font-size:15px; font-weight:bold; color:#d4af37; margin-bottom:6px; border-bottom:1px solid #d4af37; padding-bottom:4px;">${emoji} รายงานสถานการณ์ยุทธวิธี</div>
                                    <div id="view_mode_${item.id}">
                                        <div style="white-space: pre-line; line-height:1.5;">${formatCleanRedDetail(item.detail)}</div>
                                        ${gallery}
                                        <div class="admin-tools">
                                            <button class="btn-admin-act btn-edit" onclick="enableEdit(${item.id})">✏️ แก้ไข</button>
                                            <button class="btn-admin-act btn-del" onclick="deleteReport(${item.id})">🗑️ ลบ</button>
                                        </div>
                                    </div>
                                    <div id="edit_mode_${item.id}" style="display:none;">
                                        สถานการณ์: <input type="text" id="es_${item.id}" class="edit-box-input" value="${extractField(item.detail, 'สถานการณ์')}"><br>
                                        เหตุการณ์: <textarea id="ei_${item.id}" class="edit-box-input" rows="2">${extractField(item.detail, 'เหตุการณ์')}</textarea><br>
                                        การปฏิบัติ: <textarea id="ea_${item.id}" class="edit-box-input" rows="2">${extractField(item.detail, 'การปฏิบัติ')}</textarea><br>
                                        <div class="admin-tools">
                                            <button class="btn-admin-act btn-save" onclick="saveEdit(${item.id})">💾 บันทึก</button>
                                            <button class="btn-admin-act btn-cancel" onclick="cancelEdit(${item.id})">ยกเลิก</button>
                                        </div>
                                    </div>
                                </div>
                            `);
                            group.push([item.latitude, item.longitude]);
                        }
                    });
                    if (group.length > 0 && autoZoom) map.fitBounds(group, { padding: [50, 50], maxZoom: 16 });
                } else { document.getElementById('total_reports').innerText = "ไม่พบจุดรายงาน"; }
            }

            function enableEdit(id) { document.getElementById(`view_mode_${id}`).style.display = 'none'; document.getElementById(`edit_mode_${id}`).style.display = 'block'; }
            function cancelEdit(id) { document.getElementById(`view_mode_${id}`).style.display = 'block'; document.getElementById(`edit_mode_${id}`).style.display = 'none'; }
            
            async function saveEdit(id) {
                const pass = prompt("🔑 กรอกรหัสยืนยันการแก้ไข (wisarut):");
                if (pass !== "wisarut") { alert('รหัสไม่ถูกต้อง'); return; }
                const res = await fetch('/api/update-report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ passcode: pass, report_id: id, situation: document.getElementById(`es_${id}`).value, incident: document.getElementById(`ei_${id}`).value, action: document.getElementById(`ea_${id}`).value }) });
                if (res.ok) { alert('แก้ไขสำเร็จ'); verifyAdminKey(); } else alert('ล้มเหลว');
            }

            async function deleteReport(id) {
                const pass = prompt("🔑 กรอกรหัสยืนยันการลบ (wisarut):");
                if (pass !== "wisarut") { alert('รหัสไม่ถูกต้อง'); return; }
                const res = await fetch('/api/delete-report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ passcode: pass, report_id: id }) });
                if (res.ok) { alert('ลบสำเร็จ'); verifyAdminKey(); } else alert('ล้มเหลว');
            }
        </script>
    </body>
    </html>
    """

# API สำหรับส่งคำขอยิงสนับสนุน (Call For Fire) เข้ากลุ่ม LINE
@app.post("/api/send-fire-support")
def send_fire_support(payload: FireSupportPayload):
    if payload.passcode != EDIT_PASSCODE:
        raise HTTPException(status_code=403, detail="รหัสผ่านยืนยันไม่ถูกต้อง (wisarut)")

    if not CHANNEL_ACCESS_TOKEN:
        return {"status": "no_token"}

    target_id = TARGET_GROUP_ID
    if not target_id:
        try:
            r = supabase.table("line_groups").select("group_id").order("created_at", desc=True).limit(1).execute()
            if r.data: target_id = r.data[0].get("group_id")
        except Exception as e: pass
    if not target_id:
        raise HTTPException(status_code=400, detail="ไม่พบ Group ID ของ LINE")

    # อัปโหลดรูปเป้าหมาย 1 รูป (ถ้ามี)
    uploaded_target_url = None
    if payload.image_base64:
        try:
            now = datetime.now(THAILAND_TZ)
            data = payload.image_base64.split(",", 1)[1] if "," in payload.image_base64 else payload.image_base64
            b_bytes = base64.b64decode(data)
            fname = f"cff_target_{int(now.timestamp())}_{uuid.uuid4().hex[:6]}.jpg"
            supabase.storage.from_("reports").upload(path=fname, file=b_bytes, file_options={"content-type": "image/jpeg"})
            uploaded_target_url = supabase.storage.from_("reports").get_public_url(fname)
        except Exception as e:
            print(f"CFF Image Upload Error: {e}")

    flex_json = {
        "type": "bubble", "size": "mega",
        "styles": {"header": {"backgroundColor": "#1a0505"}, "body": {"backgroundColor": "#0d0404"}, "footer": {"backgroundColor": "#1a0505"}},
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "PHANTOM FIRE MISSION", "weight": "bold", "color": "#ff3838", "size": "xs", "flex": 1}, {"type": "text", "text": "CALL FOR FIRE // CFF", "weight": "bold", "color": "#d4af37", "size": "xxs", "align": "end"}]},
                {"type": "text", "text": f"🎯 ภารกิจ: {payload.target_name}", "weight": "bold", "color": "#ffffff", "size": "md", "margin": "sm"},
                {"type": "text", "text": f"อาวุธ: {payload.weapon_type}", "color": "#ff9800", "size": "xs", "weight": "bold"}
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "พิกัดเป้าหมาย:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": payload.target_mgrs, "color": "#00ffcc", "size": "xs", "weight": "bold", "flex": 7}]},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "พิกัด GPS เป้า:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": payload.target_coords, "color": "#7ee0ad", "size": "xs", "flex": 7}]},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "ที่ตั้งยิง (FOB):", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": payload.gun_mgrs, "color": "#e0e6ed", "size": "xs", "flex": 7}]},
                {"type": "separator", "color": "#4a1c1c", "margin": "md"},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "ระยะยิงจริง:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": f"{payload.distance_meters:.0f} ม. ({payload.distance_meters/1000:.2f} กม.)", "color": "#ffd700", "size": "xs", "weight": "bold", "flex": 7}]},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "มุมทิศยิง:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": f"{payload.azimuth_deg:.1f}° ({payload.azimuth_mils:.0f} Mils)", "color": "#00ffcc", "size": "xs", "weight": "bold", "flex": 7}]},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "มุมสูง (QE):", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": f"{payload.qe_mils:.0f} Mils", "color": "#00ffcc", "size": "xs", "weight": "bold", "flex": 7}]},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "เวลาตกกระทบ:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": f"ประมาณ {payload.tof_seconds} วินาที", "color": "#e0e6ed", "size": "xs", "flex": 7}]}
            ]
        },
        "footer": {
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#b71c1c", "height": "sm", "action": {"type": "uri", "label": "🌐 แผนที่วอร์รูม", "uri": "https://tactical-line-backend.onrender.com/map"}},
                {"type": "button", "style": "secondary", "color": "#331111", "height": "sm", "action": {"type": "uri", "label": "📍 นำทางเป้าหมาย", "uri": f"https://maps.google.com/?q={payload.target_coords}"}}
            ]
        }
    }

    if uploaded_target_url:
        flex_json["hero"] = {
            "type": "image", "url": uploaded_target_url, "size": "full", "aspectRatio": "16:9", "aspectMode": "cover"
        }

    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(PushMessageRequest(to=target_id, messages=[FlexMessage(alt_text=f"🚨 CALL FOR FIRE: {payload.target_name}", contents=FlexContainer.from_dict(flex_json))]))
        return {"status": "success"}
    except Exception as e:
        print(f"Fire support LINE push error: {e}")
        raise HTTPException(status_code=500, detail="Line Push Error")

# API สำหรับดึงรายงานทั้งหมด
@app.get("/api/get-all-reports")
def get_all_reports(passcode: str = ""):
    if passcode != ADMIN_PASSCODE:
        raise HTTPException(status_code=403, detail="สิทธิ์ไม่ถูกต้อง")
    try:
        res = supabase.table("reports").select("*").order("created_at", desc=True).limit(100).execute()
        return res.data
    except Exception as e:
        return []

@app.post("/api/update-report")
def update_report(payload: UpdateReportPayload):
    if payload.passcode != EDIT_PASSCODE:
        raise HTTPException(status_code=403, detail="รหัสผ่านไม่ถูกต้อง")
    try:
        res = supabase.table("reports").select("*").eq("id", payload.report_id).execute()
        old = res.data[0].get("detail", "")
        new = re.sub(r"สถานการณ์:\s*.*", f"สถานการณ์: {payload.situation}", old)
        new = re.sub(r"เหตุการณ์:\s*.*", f"เหตุการณ์: {payload.incident}", new)
        new = re.sub(r"การปฏิบัติ:\s*.*", f"การปฏิบัติ: {payload.action}", new)
        supabase.table("reports").update({"detail": new}).eq("id", payload.report_id).execute()
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error")

@app.post("/api/delete-report")
def delete_report(payload: DeleteReportPayload):
    if payload.passcode != EDIT_PASSCODE:
        raise HTTPException(status_code=403, detail="รหัสผ่านไม่ถูกต้อง")
    try:
        supabase.table("reports").delete().eq("id", payload.report_id).execute()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error")

# --- ฟังก์ชันยิง LINE Flex Message สำหรับรายงานยุทธวิธี ---
def send_tactical_flex_to_line(payload: ReportPayload, time_str: str, image_urls: list):
    if not CHANNEL_ACCESS_TOKEN: return
    target_id = TARGET_GROUP_ID
    if not target_id:
        try:
            r = supabase.table("line_groups").select("group_id").order("created_at", desc=True).limit(1).execute()
            if r.data: target_id = r.data[0].get("group_id")
        except Exception as e: pass
    if not target_id: return

    icon_emoji = payload.tactical_icon.split(" ")[0] if payload.tactical_icon else "🎯"
    flex_json = {
        "type": "bubble", "size": "mega",
        "styles": {"header": {"backgroundColor": "#0d1410"}, "body": {"backgroundColor": "#060a08"}, "footer": {"backgroundColor": "#0d1410"}},
        "header": {
            "type": "box", "layout": "vertical",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "PHANTOM SITREP FEED", "weight": "bold", "color": "#d4af37", "size": "xs", "flex": 1}, {"type": "text", "text": "FLASH // PRIORITY", "weight": "bold", "color": "#ff3838", "size": "xxs", "align": "end"}]},
                {"type": "text", "text": f"{icon_emoji} {payload.situation}", "weight": "bold", "color": "#ffffff", "size": "md", "margin": "sm"}
            ]
        },
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "เวลาบันทึก:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": time_str, "color": "#e0e6ed", "size": "xs", "flex": 7}]},
                {"type": "box", "layout": "horizontal", "contents": [{"type": "text", "text": "พิกัด MGRS:", "color": "#ff3838", "size": "xs", "weight": "bold", "flex": 3}, {"type": "text", "text": payload.mgrs or "N/A", "color": "#00ffcc", "size": "xs", "weight": "bold", "flex": 7}]},
                {"type": "separator", "color": "#334139", "margin": "md"},
                {"type": "text", "text": "เหตุการณ์:", "color": "#ff3838", "size": "xs", "weight": "bold", "margin": "sm"},
                {"type": "text", "text": payload.incident, "color": "#e0e6ed", "size": "xs", "wrap": True},
                {"type": "text", "text": "การปฏิบัติ:", "color": "#ff3838", "size": "xs", "weight": "bold", "margin": "sm"},
                {"type": "text", "text": payload.action, "color": "#e0e6ed", "size": "xs", "wrap": True}
            ]
        },
        "footer": {
            "type": "box", "layout": "horizontal", "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#d4af37", "height": "sm", "action": {"type": "uri", "label": "🌐 แผนที่เรดาร์", "uri": "https://tactical-line-backend.onrender.com/map"}},
                {"type": "button", "style": "secondary", "color": "#223328", "height": "sm", "action": {"type": "uri", "label": "📍 นำทาง", "uri": f"https://maps.google.com/?q={payload.latitude},{payload.longitude}"}}
            ]
        }
    }
    if image_urls: flex_json["hero"] = {"type": "image", "url": image_urls[0], "size": "full", "aspectRatio": "16:9", "aspectMode": "cover"}
    try:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).push_message(PushMessageRequest(to=target_id, messages=[FlexMessage(alt_text=f"🚨 รายงาน: {payload.situation}", contents=FlexContainer.from_dict(flex_json))]))
    except Exception as e: print(e)

@app.post("/api/submit-report")
async def submit_report(payload: ReportPayload):
    if payload.passcode != REPORT_PASSCODE: raise HTTPException(status_code=400, detail="รหัสผ่านผิด")
    now = datetime.now(THAILAND_TZ)
    time_str = now.strftime("%d/%m/%Y %H:%M:%S")
    urls = []
    if payload.images:
        for idx, b64 in enumerate(payload.images):
            try:
                data = b64.split(",", 1)[1] if "," in b64 else b64
                b_bytes = base64.b64decode(data)
                fname = f"tac_{int(now.timestamp())}_{uuid.uuid4().hex[:6]}_{idx}.jpg"
                supabase.storage.from_("reports").upload(path=fname, file=b_bytes, file_options={"content-type": "image/jpeg"})
                urls.append(supabase.storage.from_("reports").get_public_url(fname))
            except Exception as e: pass

    try:
        supabase.table("reports").insert({
            "user_id": payload.user_id, "report_type": "รายงานยุทธวิธี",
            "detail": f"เวลา: {time_str}\nสัญลักษณ์ยุทธวิธี: {payload.tactical_icon}\nรัศมีอันตราย: {payload.radius_meters} เมตร\nสถานการณ์: {payload.situation}\nเหตุการณ์: {payload.incident}\nพิกัด MGRS: {payload.mgrs}\nพิกัด GPS: {payload.latitude:.6f}, {payload.longitude:.6f}\nการปฏิบัติ: {payload.action}\nแผนที่ Google: https://maps.google.com/?q={payload.latitude},{payload.longitude}\nจำนวนภาพถ่าย: {len(urls)} ภาพ",
            "latitude": payload.latitude, "longitude": payload.longitude, "image_url": ",".join(urls) if urls else None
        }).execute()
        send_tactical_flex_to_line(payload, time_str, urls)
    except Exception as e: raise HTTPException(status_code=500, detail="DB Error")
    return {"status": "success"}

@app.post("/callback")
async def callback(request: Request):
    try:
        handler.handle((await request.body()).decode("utf-8"), request.headers.get("X-Line-Signature", ""))
    except Exception as e: pass
    return Response(content="OK", status_code=200)

@handler.add(JoinEvent)
def handle_join(event):
    if event.source.type == "group":
        try: supabase.table("line_groups").upsert({"group_id": event.source.group_id, "group_name": "GROUP"}).execute()
        except Exception as e: pass

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if event.source.type == "group" and event.message.text.strip().lower() == ".id":
        try:
            supabase.table("line_groups").upsert({"group_id": event.source.group_id, "group_name": "GROUP"}).execute()
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message_with_http_info(reply_message_request={"replyToken": event.reply_token, "messages": [TextMessage(text=f"🎯 บันทึก Group ID สำเร็จ:\n{event.source.group_id}")]})
        except Exception as e: pass
