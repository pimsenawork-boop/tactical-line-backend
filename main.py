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
        <!-- Leaflet CSS แผนที่ยุทธวิธี -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            :root {
                --gold-accent: #d4af37;
                --gold-glow: rgba(212, 175, 55, 0.45);
                --border-subtle: rgba(212, 175, 55, 0.35);
                --thai-red: #a51c24;
                --thai-blue: #1c2c59;
            }
            * { box-sizing: border-box; }
            
            body {
                margin: 0;
                padding: 15px;
                font-family: 'Chakra Petch', sans-serif;
                background-color: #060907;
                background-image: 
                    linear-gradient(rgba(0, 0, 0, 0.45), rgba(0, 0, 0, 0.65)),
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
                    linear-gradient(rgba(10, 15, 12, 0.8), rgba(6, 10, 8, 0.88)),
                    url('/bg.jpg');
                background-size: cover;
                background-position: center center;
                border: 1.5px solid var(--border-subtle);
                border-radius: 14px;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9), 0 0 25px rgba(212, 175, 55, 0.15);
                padding: 24px 22px;
                position: relative;
                overflow: hidden;
            }

            .thai-ribbon {
                position: absolute;
                top: 0;
                right: 0;
                width: 85px;
                height: 5px;
                background: linear-gradient(90deg, 
                    var(--thai-red) 0% 20%, 
                    #fff 20% 40%, 
                    var(--thai-blue) 40% 60%, 
                    #fff 60% 80%, 
                    var(--thai-red) 80% 100%);
            }

            .header-badge {
                text-align: center;
                margin-bottom: 16px;
                position: relative;
            }

            .title-main {
                font-size: 21px;
                font-weight: 700;
                color: var(--gold-accent);
                letter-spacing: 2.5px;
                text-transform: uppercase;
                margin: 0;
                text-shadow: 0 2px 5px rgba(0, 0, 0, 0.9);
            }
            .title-sub {
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                color: #8da196;
                letter-spacing: 1.2px;
                margin-top: 3px;
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
                font-size: 12.5px;
                font-weight: 600;
                color: #a2b5aa;
                margin-bottom: 5px;
                letter-spacing: 0.5px;
                text-shadow: 0 1px 3px rgba(0,0,0,0.8);
            }

            input, textarea {
                width: 100%;
                background-image: 
                    linear-gradient(rgba(5, 8, 6, 0.78), rgba(5, 8, 6, 0.88)),
                    url('/bg.jpg');
                background-size: cover;
                background-position: center;
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px;
                color: #ffffff;
                padding: 10px 12px;
                font-family: 'Chakra Petch', sans-serif;
                font-size: 14px;
                transition: all 0.25s ease;
            }
            input:focus, textarea:focus {
                outline: none;
                border-color: var(--gold-accent);
                background-image: 
                    linear-gradient(rgba(12, 18, 14, 0.7), rgba(12, 18, 14, 0.85)),
                    url('/bg.jpg');
                box-shadow: 0 0 12px var(--gold-glow);
            }
            .readonly-input {
                font-family: 'Share Tech Mono', monospace;
                color: #7ee0ad;
                background-image: 
                    linear-gradient(rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0.8)),
                    url('/bg.jpg');
                border-color: rgba(255, 255, 255, 0.08);
            }
            textarea { resize: vertical; min-height: 55px; }

            /* สไตล์ปุ่มเครื่องมือ GPS & Map */
            .gps-tools {
                display: flex;
                gap: 6px;
                margin-top: 5px;
            }
            .tool-btn {
                flex: 1;
                background: rgba(212, 175, 55, 0.15);
                border: 1px solid rgba(212, 175, 55, 0.4);
                color: var(--gold-accent);
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 600;
                border-radius: 5px;
                cursor: pointer;
                transition: 0.2s;
                text-align: center;
            }
            .tool-btn:hover {
                background: rgba(212, 175, 55, 0.3);
                box-shadow: 0 0 8px var(--gold-glow);
            }

            /* กล่องแผนที่ดาวเทียม/ภูมิประเทศ Modal */
            #map-modal {
                display: none;
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.85);
                z-index: 9999;
                padding: 15px;
                justify-content: center;
                align-items: center;
            }
            .map-box {
                width: 100%;
                max-width: 500px;
                height: 80vh;
                background: #0d1410;
                border: 1.5px solid var(--gold-accent);
                border-radius: 12px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
                box-shadow: 0 0 30px rgba(0,0,0,0.9);
            }
            .map-header {
                padding: 10px 15px;
                background: rgba(10,15,12,0.9);
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--border-subtle);
            }
            .map-header h3 { margin: 0; font-size: 14px; color: var(--gold-accent); }
            #tactical-map { flex: 1; width: 100%; }
            .map-footer {
                padding: 10px;
                background: rgba(10,15,12,0.9);
                text-align: center;
                border-top: 1px solid var(--border-subtle);
            }

            /* 5 ช่องสี่เหลี่ยมแนบภาพพร้อมปุ่มลบ/สลับรูป */
            .img-grid {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 8px;
                margin-top: 6px;
            }
            .img-slot {
                aspect-ratio: 1 / 1;
                background-image: 
                    linear-gradient(rgba(5, 8, 6, 0.65), rgba(5, 8, 6, 0.75)),
                    url('/bg.jpg');
                background-size: cover;
                background-position: center;
                border: 1px dashed rgba(212, 175, 55, 0.4);
                border-radius: 7px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                overflow: hidden;
                position: relative;
                transition: 0.2s;
            }
            .img-slot:hover {
                border-color: var(--gold-accent);
                box-shadow: 0 0 10px var(--gold-glow);
            }
            .img-slot img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            .img-slot span {
                font-size: 20px;
                color: var(--gold-accent);
            }
            .btn-remove-img {
                position: absolute;
                top: 2px;
                right: 2px;
                background: rgba(165, 28, 36, 0.85);
                color: #fff;
                border: 1px solid #fff;
                border-radius: 50%;
                width: 18px;
                height: 18px;
                font-size: 11px;
                line-height: 16px;
                text-align: center;
                cursor: pointer;
                display: none;
                z-index: 10;
            }
            .img-slot.has-img .btn-remove-img { display: block; }

            .btn-action {
                width: 100%;
                background: linear-gradient(180deg, #a88424 0%, #614a10 100%);
                border: 1px solid var(--gold-accent);
                color: #fff;
                padding: 12px;
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 2px;
                cursor: pointer;
                border-radius: 8px;
                margin-top: 15px;
                text-transform: uppercase;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
                transition: all 0.25s ease;
            }
            .btn-action:hover {
                background: linear-gradient(180deg, #c49d32 0%, #7d6017 100%);
                box-shadow: 0 0 15px var(--gold-glow);
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
                font-size: 11px;
                color: #8da196;
                margin-top: 4px;
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
                    <input type="text" id="time_display" class="readonly-input" readonly>
                </div>
                <div class="form-group">
                    <label>3. พิกัด GPS (LAT, LON):</label>
                    <input type="text" id="coords_display" placeholder="14.xxxxxx, 102.xxxxxx" onchange="manualCoordsInput(this.value)">
                    <div class="gps-tools">
                        <button type="button" class="tool-btn" onclick="getAutoGPS()">🛰️ AUTO GPS</button>
                        <button type="button" class="tool-btn" onclick="openMapModal()">🗺️ ปักหมุดแผนที่</button>
                    </div>
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

        <!-- หน้าต่าง Modal สำหรับเลือกและลากหมุดบนแผนที่ภูมิประเทศ/ดาวเทียม -->
        <div id="map-modal">
            <div class="map-box">
                <div class="map-header">
                    <h3>🗺️ TACTICAL MAP PINPOINT</h3>
                    <span style="cursor:pointer; color:#e57373; font-weight:bold; font-size:18px;" onclick="closeMapModal()">✕</span>
                </div>
                <div id="tactical-map"></div>
                <div class="map-footer">
                    <div id="modal_coord_text" style="color: #7ee0ad; font-family:'Share Tech Mono'; font-size:13px; margin-bottom:8px;">
                        พิกัด: 0.000000, 0.000000
                    </div>
                    <button type="button" class="tool-btn" style="padding: 8px 20px; font-size:13px;" onclick="confirmMapPin()">🎯 ยืนยันพิกัดนี้</button>
                </div>
            </div>
        </div>

        <!-- Leaflet JS สำหรับระบบแผนที่ -->
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            let userLat = 14.967565;
            let userLon = 102.081882;
            let imagesArray = [null, null, null, null, null];
            let activeSlotIndex = 0;
            let map, marker;

            function updateTime() {
                const now = new Date();
                document.getElementById('time_display').value = now.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok' });
            }
            updateTime();

            // ดึง GPS อัตโนมัติจากเครื่อง
            function getAutoGPS() {
                const status = document.getElementById('gps_status');
                status.innerText = "⚡ GPS: กำลังตรวจจับดาวเทียม...";
                status.style.color = "#d4af37";

                if (navigator.geolocation) {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            userLat = pos.coords.latitude;
                            userLon = pos.coords.longitude;
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
            }

            function manualCoordsInput(val) {
                const parts = val.split(',');
                if (parts.length === 2) {
                    const lat = parseFloat(parts[0].trim());
                    const lon = parseFloat(parts[1].trim());
                    if (!isNaN(lat) && !isNaN(lon)) {
                        userLat = lat;
                        userLon = lon;
                        document.getElementById('gps_status').innerText = "📍 พิกัด: กำหนดตำแหน่งเอง";
                        document.getElementById('gps_status').style.color = "#d4af37";
                    }
                }
            }

            // ระบบแผนที่ Leaflet Satellite/Hybrid
            function initMap() {
                if (!map) {
                    map = L.map('tactical-map').setView([userLat, userLon], 15);
                    
                    // เลเยอร์แผนที่ผสม (ภูมิประเทศ + ถนน)
                    L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
                        maxZoom: 20,
                        subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
                    }).addTo(map);

                    // มาร์กเกอร์ลากได้
                    marker = L.marker([userLat, userLon], { draggable: true }).addTo(map);

                    marker.on('dragend', function (e) {
                        const pos = marker.getLatLng();
                        updateModalCoordText(pos.lat, pos.lng);
                    });

                    map.on('click', function(e) {
                        marker.setLatLng(e.latlng);
                        updateModalCoordText(e.latlng.lat, e.latlng.lng);
                    });
                } else {
                    map.setView([userLat, userLon], 15);
                    marker.setLatLng([userLat, userLon]);
                }
                updateModalCoordText(userLat, userLon);
            }

            function updateModalCoordText(lat, lon) {
                document.getElementById('modal_coord_text').innerText = `พิกัด: ${lat.toFixed(6)}, ${lon.toFixed(6)}`;
            }

            function openMapModal() {
                document.getElementById('map-modal').style.display = 'flex';
                setTimeout(() => {
                    initMap();
                    map.invalidateSize();
                }, 200);
            }

            function closeMapModal() {
                document.getElementById('map-modal').style.display = 'none';
            }

            function confirmMapPin() {
                const pos = marker.getLatLng();
                userLat = pos.lat;
                userLon = pos.lng;
                updateCoordsDisplay();
                document.getElementById('gps_status').innerText = "🎯 พิกัด: ปักหมุดแผนที่ภูมิประเทศ";
                document.getElementById('gps_status').style.color = "#7ee0ad";
                closeMapModal();
            }

            // ระบบจัดการรูปภาพรายช่อง (เปลี่ยน/ลบ/เลือกใหม่)
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
                event.stopPropagation(); // ไม่ให้ไปเปิดหน้าต่างเลือกไฟล์
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

    try:
        report_data = {
            "user_id": payload.user_id,
            "report_type": "รายงานยุทธวิธี (PHANTOM HUD)",
            "detail": (
                f"เวลา: {time_str}\n"
                f"1. สถานการณ์: {payload.situation}\n"
                f"3. เหตุการณ์: {payload.incident}\n"
                f"5. การปฏิบัติ: {payload.action}\n"
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
