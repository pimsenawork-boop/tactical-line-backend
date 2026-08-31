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

# --- หน้าศูนย์รวมแผนที่ยุทธศาสตร์ (Combat Operations Center พร้อมระบบ CFF และวอร์รูมสมบูรณ์) ---
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

            .huge-tactical-pin { font-size: 34px !important; text-align: center; filter: drop-shadow(0 0 4px #000) drop-shadow(0 2px 6px rgba(0,0,0,0.95)); cursor: pointer; line-height: 34px; border: 1.5px solid rgba(255,255,255,0.4); border-radius: 50%; background: rgba(10,15,12,0.6); padding: 2px; }

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

        <div class="left-sidebar-container" id="left_sidebar" style="display: none;">
            
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
                    <div class="fire-row"><span>มุมสูงประมาณการ:</span><span class="fire-highlight" id="f_qe">0 Mils</span></div>
                    <div class="fire-row"><span>เวลาตกกระทบ (TOF):</span><span class="fire-highlight" id="f_tof">~0 วินาที</span></div>
                    <div class="fire-row"><span>สถานะระยะยิง:</span><span id="f_status" style="color:#8da196;">รอระบุพิกัด</span></div>

                    <button type="button" class="btn-fire-action" onclick="sendFireSupportToLinePrompt()">🚀 ส่งคำสั่งยิงสนับสนุน (LINE)</button>
                </div>
            </div>

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
        <script
