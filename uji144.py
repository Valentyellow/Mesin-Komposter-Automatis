import socket
import json
import urllib.parse
import os
from datetime import datetime

class SmartComposter:
    def __init__(self):
        self.suhu_kompor = 0.0  
        self.suhu_ruang = 0.0   
        self.kelembaban = 0.0   
        self.berat_aktual = 0.0  
        
        self.berat_awal = 0.0
        self.kelembapan_awal = 0.0
        self.kategori_berat = "-"
        self.kategori_lembap = "-"
        
        self.berat_akhir = 0.0
        self.persentase_susut = 0.0
        
        self.fase_aktif = "IDLE"
        self.mode_aktif = "AUTO"
        
        self.target_suhu = 75.0 
        self.target_waktu = 600 
        self.target_grinding = 10 
        self.target_pengaduk = 2 # Default Pengaduk ON 2 detik
        
        self.sisa_waktu_detik = 0
        self.temp_reached = False
        self.overheat_fan = False
        
        self.perintah_tare = False 
        self.terminal_logs = []

    def log(self, pesan):
        waktu = datetime.now().strftime("%H:%M:%S")
        self.terminal_logs.append(f"[{waktu}] {pesan}")
        if len(self.terminal_logs) > 50:
            self.terminal_logs.pop(0)

alat = SmartComposter()

# NAMA FILE BARU AGAR TIDAK BENTROK DENGAN CSV LAMA
csv_utama = "log_fsm_lengkap.csv" 
if not os.path.exists(csv_utama):
    with open(csv_utama, "w") as f:
        # HEADER BARU (Sesuai referensi data fsm1.csv menggunakan pemisah Semicolon/Titik Koma)
        f.write("Waktu;Fase;Mode;Kategori_Sampah;Target_Suhu;Suhu_Heater;Suhu_Ruang;Kelembaban;Berat_Aktual;Berat_Awal;Berat_Akhir;Penyusutan;R_Heater;R_Chopper;R_Pengaduk;R_Fan1;R_Fan2;R_Fan3;Timer_Mundur_Grinder;Timer_Mundur_Heater;Timer_Mundur_Cooling\n")

csv_rulebased = "data_pengujian_rulebased.csv"
if not os.path.exists(csv_rulebased):
    with open(csv_rulebased, "w") as f:
        f.write("NO,BOBOT,KELEMBAPAN,SET DURASI,SUHU MAKS,DURASI,LEVEL BERAT AWAL,LEVEL BERAT AKHIR\n")

def count_csv2_lines():
    if os.path.exists(csv_rulebased):
        with open(csv_rulebased, "r") as f:
            return sum(1 for row in f)
    return 1

html_page = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EcoSync - Smart Composter Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg-color: #0f172a; --card-bg: #1e293b; --accent-green: #10b981; --accent-blue: #3b82f6; --accent-orange: #f59e0b; --accent-red: #ef4444; --accent-purple: #8b5cf6; --text-main: #f8fafc; --text-muted: #94a3b8; --border-color: #334155; }
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: var(--bg-color); margin: 0; padding: 0; color: var(--text-main); }
        .header { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); text-align: center; padding: 25px 20px; border-bottom: 2px solid var(--border-color); box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); }
        .header h1 { margin: 0 0 5px 0; font-size: 1.5rem; color: #fff; }
        .container { padding: 20px; max-width: 800px; margin: auto; }
        .card { background: var(--card-bg); border-radius: 16px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); border: 1px solid var(--border-color); }
        .card h3 { margin-top: 0; font-size: 1rem; display: flex; align-items: center; gap: 8px; margin-bottom: 15px;}
        
        .card.rule-mode { border-top: 4px solid var(--accent-purple); }
        .card.manual-mode { border-top: 4px solid var(--accent-orange); }
        
        .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center; margin-bottom: 12px;}
        .sensor-box { background: rgba(15, 23, 42, 0.6); padding: 15px 10px; border-radius: 12px; border: 1px solid var(--border-color); transition: transform 0.2s; }
        .sensor-val { font-size: 1.3rem; font-weight: 700; color: var(--accent-blue); margin-top: 6px; }
        .label { font-size: 0.65rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; }
        
        .status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 700; }
        .status-on { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .status-off { background: rgba(239, 68, 68, 0.15); color: #f87171; }
        .dot { width: 8px; height: 8px; border-radius: 50%; }
        .status-on .dot { background: #34d399; box-shadow: 0 0 8px #34d399; animation: pulse 1.5s infinite; }
        .status-off .dot { background: #f87171; }
        @keyframes pulse { 0% { transform: scale(0.95); opacity: 0.8; } 50% { transform: scale(1.2); opacity: 1; } 100% { transform: scale(0.95); opacity: 0.8; } }
        
        input[type="number"] { width: 50px; padding: 8px; background: #0f172a; border-radius: 6px; border: 1px solid var(--border-color); color: white; font-weight: bold; text-align: center; }
        input[type="number"].input-large { width: 100%; box-sizing: border-box; }
        
        button { width: 100%; color: white; border: none; padding: 12px; font-weight: 700; border-radius: 10px; cursor: pointer; transition: all 0.2s; font-size: 0.9rem; display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 8px; }
        button:hover { filter: brightness(1.1); transform: translateY(-2px); }
        
        .btn-rule { background: linear-gradient(135deg, #8b5cf6, #6d28d9); padding: 12px;}
        .btn-autorun { background: linear-gradient(135deg, #059669, #10b981); font-size: 1rem; padding: 14px; }
        .btn-heater { background: linear-gradient(135deg, #f59e0b, #d97706); font-size: 1rem; padding: 14px; }
        .btn-stop { background: linear-gradient(135deg, var(--accent-red), #dc2626); }
        .btn-download { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
        .btn-tare { background: linear-gradient(135deg, var(--accent-orange), #d97706); width: auto; padding: 8px 15px; font-size: 0.75rem; margin: 0; }
        
        .terminal-container { background: #090d16; border-radius: 12px; border: 1px solid var(--border-color); overflow: hidden; margin-top: 20px;}
        .terminal { background: transparent; color: #34d399; font-family: monospace; padding: 15px; height: 160px; overflow-y: auto; font-size: 0.85rem; line-height: 1.5; margin: 0; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="header">
        <h1>EcoSync Dashboard</h1>
        <p style="color:var(--text-muted); font-size:0.85rem;">Update: Format CSV FSM (Timer Split & Semicolon Format)</p>
    </div>
    
    <div class="container">
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 15px;">
                <h3 style="margin:0;">📊 MONITORING SENSOR</h3>
                <button class="btn-tare" onclick="tareTimbangan()">⚖️ RESET TARE</button>
            </div>
            
            <p style="font-size: 0.75rem; color: var(--accent-orange); margin-top: -5px; margin-bottom: 15px;">
               <i>*Note: Loadcell terpisah. Angka berat real-time tidak mempengaruhi proses jika sudah di Kunci.</i>
            </p>

            <div class="grid-4">
                <div class="sensor-box"><div class="label">🔥 SUHU HEATER (DS)</div><div class="sensor-val" id="suhu_kompor" style="color: #ef4444;">--</div></div>
                <div class="sensor-box"><div class="label">🌡️ SUHU RUANG (DHT)</div><div class="sensor-val" id="suhu_ruang" style="color: #3b82f6;">--</div></div>
                <div class="sensor-box"><div class="label">💧 KELEMBAPAN (DHT)</div><div class="sensor-val" id="lembab">--</div></div>
                <div class="sensor-box"><div class="label">⚖️ BERAT AKTUAL</div><div class="sensor-val" id="berat">--</div></div>
            </div>

            <div class="grid-4" style="margin-top: 15px;">
                <div class="sensor-box"><div class="label">⚙️ CHOPPER</div><div id="motor" style="margin-top:8px;">--</div></div>
                <div class="sensor-box"><div class="label">🔥 HEATER</div><div id="heater" style="margin-top:8px;">--</div></div>
                <div class="sensor-box"><div class="label">🔄 STIRRER</div><div id="pengaduk" style="margin-top:8px;">--</div></div>
                <div class="sensor-box"><div class="label">💨 FANS KIPAS</div><div id="fan" style="margin-top:8px;">--</div></div>
            </div>
            
            <div style="text-align:center; margin-top: 15px;">
                <span class="label">Status Mesin Saat Ini: </span>
                <span id="active_mode" style="color: var(--accent-orange); font-weight: bold; font-size: 1.1rem; padding: 4px 10px; border: 1px solid var(--accent-orange); border-radius: 8px;">STANDBY</span>
            </div>

            <div style="text-align:center; margin-top: 15px; background: rgba(0,0,0,0.3); padding: 12px; border-radius: 8px; border: 1px dashed var(--border-color);">
                <span class="label" style="color: var(--accent-orange);">⏳ SISA WAKTU PROSES (TIMER): </span>
                <b id="ui_timer" style="font-size: 1.3rem; color: #fff; letter-spacing: 2px; display: block; margin-top: 5px;">00:00</b>
            </div>
        </div>

        <div class="card rule-mode">
            <h3 style="color: var(--accent-purple);">📋 ALUR PENGUJIAN FSM BERURUTAN</h3>
            
            <div style="background: rgba(15, 23, 42, 0.6); padding: 12px; border-radius: 10px; border: 1px solid var(--border-color); margin-bottom: 15px;">
                <p style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0; margin-bottom: 10px;">
                    Isi berat manual (Gram) untuk tes manipulasi level berat. Kosongkan untuk pakai loadcell otomatis.
                </p>
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 8px; margin-bottom: 10px;">
                    <input type="number" id="in_berat_manual" class="input-large" placeholder="Berat (Auto)">
                    <button class="btn-rule" onclick="kunciDataAwal()" style="margin: 0;">1. TIMBANG AWAL & KUNCI</button>
                </div>
                
                <div style="background: rgba(16, 185, 129, 0.15); padding: 10px; border-radius: 8px; text-align: center; margin-top: 12px; border: 1px solid #10b981;">
                   <span class="label" style="color:#34d399;">KONDISI SAMPAH TERKUNCI:</span><br>
                   <b id="ui_status_sampah" style="font-size: 1.1rem; color: #fff;">BELUM ADA DATA</b>
                </div>
            </div>
            
            <div style="background: rgba(15, 23, 42, 0.6); padding: 12px; border-radius: 10px; border: 1px solid var(--border-color); margin-bottom: 15px;">
                <div style="text-align:center; margin-bottom:10px;">
                    <span class="label">⚙️ TARGET PARAMETER MESIN:</span>
                </div>
                <div style="display:flex; gap:10px; justify-content:center; align-items:center; margin-bottom:15px;">
                    <div><span class="label">Suhu (°C):</span><br><input type="number" id="in_suhu" value="75"></div>
                    <div><span class="label">Grind (Dtk):</span><br><input type="number" id="in_grind" value="10"></div>
                    <div><span class="label">Drying (Dtk):</span><br><input type="number" id="in_waktu" value="600"></div>
                    <div><span class="label">Aduk (Dtk):</span><br><input type="number" id="in_aduk" value="2"></div>
                </div>
                
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    <button class="btn-autorun" onclick="startGrinding()">2. MULAI GRINDING</button>
                    <button class="btn-heater" onclick="startDrying()">3. LANJUT HEATER</button>
                </div>
            </div>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 8px;">
                    <input type="number" id="in_berat_akhir_manual" class="input-large" placeholder="Akhir (Auto)">
                    <button style="background: #3b82f6; margin: 0;" onclick="kunciDataAkhir()">4. KUNCI AKHIR (<span id="ui_b_akhir">0g</span>)</button>
                </div>
                <button style="background: #10b981; margin: 0;" onclick="simpanTabelDosen()">5. SIMPAN KE TABEL</button>
            </div>
        </div>

        <div class="card manual-mode">
            <h3 style="color: var(--accent-orange);">⚙️ TES MANUAL KOMPONEN</h3>
            <p style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0; text-align:center;">
                <i>*Durasi tes manual mengikuti angka di input form atas.</i>
            </p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <button style="background: #7e22ce;" onclick="startManual('GRINDING')">⚙️ TES CHOPPER</button>
                <button style="background: #0369a1;" onclick="startManual('COOLING')">❄️ TES KIPAS (10s)</button>
                <button style="background: #dc2626;" onclick="startManual('TES_HEATER')">🔥 HEATER (3s)</button>
                <button style="background: #10b981;" onclick="startManual('TES_PENGADUK')">🔄 TES STIRRER</button>
            </div>
        </div>

        <button class="btn-stop" onclick="stopProses()" style="margin-bottom:20px;">🛑 HENTIKAN MESIN (STANDBY / RESET)</button>
        
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
            <a href="/download_csv?file=utama" target="_blank" style="text-decoration: none;">
                <button class="btn-download" style="background:#475569;">📥 UNDUH LOG UTAMA</button>
            </a>
            <a href="/download_csv?file=dosen" target="_blank" style="text-decoration: none;">
                <button class="btn-download">📥 UNDUH TABEL DOSEN</button>
            </a>
        </div>

        <div class="terminal-container">
            <pre class="terminal" id="terminal_box">Menunggu koneksi dari ESP32...</pre>
        </div>
    </div>

    <script>
        function sendCmd(queryStr) { fetch(queryStr).then(() => console.log("Perintah: " + queryStr)); }
        function tareTimbangan() { sendCmd('/tare'); }
        
        function kunciDataAwal() {
            let berat_man = document.getElementById('in_berat_manual').value;
            fetch(`/kunci_awal?berat_manual=${berat_man}`).then(res => res.json()).then(data => {
                let infoStatus = `SAMPAH ${data.k_lembap.toUpperCase()} & ${data.k_berat.toUpperCase()} (${data.b_awal}g)`;
                if(data.is_manual) infoStatus += " [MANUAL]";
                
                document.getElementById('ui_status_sampah').innerText = infoStatus;
                document.getElementById('in_suhu').value = data.rec_suhu;
                document.getElementById('in_grind').value = data.rec_grinding;
                document.getElementById('in_waktu').value = data.rec_waktu;
                document.getElementById('in_aduk').value = data.rec_aduk;
                
                document.getElementById('in_berat_manual').value = ""; 
                alert("Data Terkunci! Anda bisa melanjutkan proses '2. MULAI GRINDING'.");
            });
        }
        
        function startGrinding() { 
            let s = document.getElementById('in_suhu').value;
            let g = document.getElementById('in_grind').value;
            let w = document.getElementById('in_waktu').value;
            let a = document.getElementById('in_aduk').value;
            sendCmd(`/input?fase=GRINDING&mode=AUTO&t_suhu=${s}&t_grinding=${g}&t_waktu=${w}&t_aduk=${a}`); 
        }

        function startDrying() { 
            let s = document.getElementById('in_suhu').value;
            let g = document.getElementById('in_grind').value;
            let w = document.getElementById('in_waktu').value;
            let a = document.getElementById('in_aduk').value;
            sendCmd(`/input?fase=DRYING&mode=AUTO&t_suhu=${s}&t_grinding=${g}&t_waktu=${w}&t_aduk=${a}`); 
        }

        function kunciDataAkhir() {
            let berat_man = document.getElementById('in_berat_akhir_manual').value;
            fetch(`/kunci_akhir?berat_manual=${berat_man}`).then(res => res.json()).then(data => {
                document.getElementById('ui_b_akhir').innerText = data.b_akhir + 'g';
                document.getElementById('in_berat_akhir_manual').value = ""; 
                alert("Berat Akhir (" + data.b_akhir + "g) Terkunci!");
            });
        }
        
        function simpanTabelDosen() {
            let s = document.getElementById('in_suhu').value;
            let w = document.getElementById('in_waktu').value;
            fetch(`/simpan_tabel_dosen?t_suhu=${s}&t_waktu=${w}`).then(res => res.text()).then(data => {
                alert(data);
            });
        }

        function startManual(fase) { 
            let g = document.getElementById('in_grind').value;
            let a = document.getElementById('in_aduk').value;
            let w_target = 10;
            if (fase === 'GRINDING' || fase === 'TES_GRINDING') w_target = g;
            else if (fase === 'TES_PENGADUK') w_target = a;
            else if (fase === 'TES_HEATER') w_target = 3;
            else if (fase === 'COOLING') w_target = 10;
            
            sendCmd(`/input?fase=${fase}&mode=MANUAL&t_waktu=${w_target}&t_grinding=${g}&t_aduk=${a}`); 
        }
        
        function stopProses() { sendCmd('/input?fase=IDLE&mode=AUTO&t_suhu=0&t_grinding=0&t_waktu=0'); }

        function formatLED(status) {
            return status === "ON" ? '<div class="status-badge status-on"><div class="dot"></div>ON</div>' : '<div class="status-badge status-off"><div class="dot"></div>OFF</div>';
        }

        setInterval(() => {
            fetch('/data')
            .then(res => res.json())
            .then(data => {
                document.getElementById('suhu_kompor').innerText = Number(data.suhu_kompor).toFixed(1) + ' °C';
                document.getElementById('suhu_ruang').innerText = Number(data.suhu_ruang).toFixed(1) + ' °C';
                document.getElementById('lembab').innerText = Number(data.lembab).toFixed(1) + ' %';
                document.getElementById('berat').innerText = Number(data.berat).toFixed(0) + ' g'; 

                document.getElementById('motor').innerHTML = formatLED((data.fase === "GRINDING") ? "ON" : "OFF");
                document.getElementById('heater').innerHTML = formatLED((data.fase === "DRYING" || data.fase === "TES_HEATER") ? "ON" : "OFF");
                document.getElementById('pengaduk').innerHTML = formatLED((data.fase === "DRYING" || data.fase === "TES_PENGADUK") ? "ON" : "OFF");
                document.getElementById('fan').innerHTML = formatLED((data.fase === "COOLING" || (data.fase === "DRYING" && data.overheat_fan)) ? "ON" : "OFF");
                
                let m = data.fase === "IDLE" ? "STANDBY" : `${data.fase}`;
                document.getElementById('active_mode').innerText = m;
                
                let sisa = data.sisa_waktu || 0;
                if(sisa > 0) {
                    let mnt = Math.floor(sisa / 60);
                    let dtk = sisa % 60;
                    document.getElementById('ui_timer').innerText = (mnt < 10 ? "0"+mnt : mnt) + ":" + (dtk < 10 ? "0"+dtk : dtk);
                    document.getElementById('ui_timer').style.color = "#fff";
                } else {
                    if(data.fase === "DRYING" && !data.temp_reached) {
                        document.getElementById('ui_timer').innerText = "🔥 MEMANASKAN AWAL...";
                        document.getElementById('ui_timer').style.color = "#f87171";
                    } else {
                        document.getElementById('ui_timer').innerText = "00:00";
                        document.getElementById('ui_timer').style.color = "#94a3b8";
                    }
                }
                
                let term = document.getElementById('terminal_box');
                term.innerText = data.logs.join('\\n');
                term.scrollTop = term.scrollHeight;
            });
        }, 500); 
    </script>
</body>
</html>
"""

def start_server():
    HOST = '0.0.0.0'
    PORT = 8080
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(5)
    
    print("\n" + "="*60)
    print(" SERVER IOT READY! (CUSTOM DURASI GRINDER & MOTOR AKTIF) ")
    print(f" Buka browser di http://localhost:{PORT}")
    print("="*60 + "\n")

    while True:
        try:
            conn, addr = s.accept()
            req = conn.recv(1024).decode('utf-8')
            lines = req.split('\r\n')
            if not lines or lines[0] == "": 
                conn.close(); continue
            
            req_line = lines[0] 

            if 'GET /tare' in req_line:
                alat.perintah_tare = True
                conn.sendall("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n".encode('utf-8'))

            elif 'GET /kunci_awal' in req_line:
                parsed = urllib.parse.urlparse(req_line.split(' ')[1])
                params = urllib.parse.parse_qs(parsed.query)
                b_manual = params.get('berat_manual', [''])[0]
                is_manual_mode = False
                
                if b_manual and b_manual.replace('.', '', 1).isdigit() and float(b_manual) > 0:
                    alat.berat_awal = float(b_manual)
                    is_manual_mode = True
                    alat.log(f">>> [OVERRIDE] Berat Awal Manual: {alat.berat_awal}g")
                else:
                    alat.berat_awal = alat.berat_aktual
                
                alat.kelembapan_awal = alat.kelembaban
                
                if alat.berat_awal <= 65: alat.kategori_berat = "Ringan"
                elif alat.berat_awal <= 85: alat.kategori_berat = "Sedang"
                else: alat.kategori_berat = "Penuh/Basah"
                    
                if alat.kelembapan_awal <= 75.0: alat.kategori_lembap = "Kering"
                else: alat.kategori_lembap = "Basah"
                
                # --- UPDATE DURASI GRINDING: Ringan=10, Sedang=15, Penuh=20 ---
                r_suhu, r_waktu, r_grinding = 75, 600, 10
                if alat.kategori_berat == "Ringan" and alat.kategori_lembap == "Kering": 
                    r_suhu, r_waktu, r_grinding = 70, 480, 10   
                elif alat.kategori_berat == "Ringan" and alat.kategori_lembap == "Basah": 
                    r_suhu, r_waktu, r_grinding = 75, 600, 10   
                elif alat.kategori_berat == "Sedang" and alat.kategori_lembap == "Kering": 
                    r_suhu, r_waktu, r_grinding = 75, 600, 15   
                elif alat.kategori_berat == "Sedang" and alat.kategori_lembap == "Basah": 
                    r_suhu, r_waktu, r_grinding = 75, 720, 15   
                elif alat.kategori_berat == "Penuh/Basah" and alat.kategori_lembap == "Kering": 
                    r_suhu, r_waktu, r_grinding = 75, 720, 20  
                elif alat.kategori_berat == "Penuh/Basah" and alat.kategori_lembap == "Basah": 
                    r_suhu, r_waktu, r_grinding = 75, 900, 20  
                
                res_body = json.dumps({
                    "b_awal": alat.berat_awal, "k_berat": alat.kategori_berat,
                    "l_awal": alat.kelembapan_awal, "k_lembap": alat.kategori_lembap,
                    "rec_suhu": r_suhu, "rec_waktu": r_waktu, "rec_grinding": r_grinding,
                    "rec_aduk": 2, 
                    "is_manual": is_manual_mode
                })
                conn.sendall(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{res_body}".encode('utf-8'))
                
            elif 'GET /kunci_akhir' in req_line:
                parsed = urllib.parse.urlparse(req_line.split(' ')[1])
                params = urllib.parse.parse_qs(parsed.query)
                b_manual = params.get('berat_manual', [''])[0]
                
                if b_manual and b_manual.replace('.', '', 1).isdigit() and float(b_manual) > 0:
                    alat.berat_akhir = float(b_manual)
                    alat.log(f">>> [OVERRIDE] Berat Akhir Manual: {alat.berat_akhir}g")
                else:
                    alat.berat_akhir = alat.berat_aktual
                    
                if alat.berat_awal > 0:
                    alat.persentase_susut = round(((alat.berat_awal - alat.berat_akhir) / alat.berat_awal) * 100.0, 2)
                    
                res_body = json.dumps({"b_akhir": alat.berat_akhir})
                conn.sendall(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{res_body}".encode('utf-8'))

            elif 'GET /simpan_tabel_dosen' in req_line:
                parsed = urllib.parse.urlparse(req_line.split(' ')[1])
                params = urllib.parse.parse_qs(parsed.query)
                set_suhu = params.get('t_suhu', ['0'])[0]
                set_waktu = params.get('t_waktu', ['0'])[0]
                
                no_id = count_csv2_lines()
                lvl_b_awal = f"{alat.kategori_berat} ({alat.berat_awal}g)"
                lvl_b_akhir = f"Kompos ({alat.berat_akhir}g)"
                
                baris_csv = f"{no_id},{alat.berat_awal},{alat.kelembapan_awal},{set_waktu},{set_suhu},{set_waktu},{lvl_b_awal},{lvl_b_akhir}\n"
                with open(csv_rulebased, "a") as f: f.write(baris_csv)
                conn.sendall("HTTP/1.1 200 OK\r\n\r\nData berhasil disimpan ke Tabel Dosen!".encode('utf-8'))

            elif 'GET /input' in req_line:
                parsed = urllib.parse.urlparse(req_line.split(' ')[1])
                params = urllib.parse.parse_qs(parsed.query)
                fase = params.get('fase', ['IDLE'])[0]
                mode = params.get('mode', ['AUTO'])[0]
                
                try: alat.target_suhu = float(params.get('t_suhu', [75.0])[0])
                except: pass
                try: alat.target_waktu = int(params.get('t_waktu', [10])[0])
                except: pass
                try: alat.target_grinding = int(params.get('t_grinding', [10])[0])
                except: pass
                try: alat.target_pengaduk = int(params.get('t_aduk', [2])[0])
                except: pass
                
                alat.mode_aktif = mode
                alat.fase_aktif = fase
                alat.sisa_waktu_detik = 0 
                alat.temp_reached = False
                
                alat.log(f">>> TRIGGER DITEKAN: Memulai fase {fase}")
                conn.sendall("HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n".encode('utf-8'))

            elif 'GET /download_csv' in req_line:
                parsed = urllib.parse.urlparse(req_line.split(' ')[1])
                params = urllib.parse.parse_qs(parsed.query)
                file_req = params.get('file', ['utama'])[0]
                target_file = csv_utama if file_req == "utama" else csv_rulebased
                
                try:
                    with open(target_file, "r") as f: csv_content = f.read()
                    http_res = ("HTTP/1.1 200 OK\r\nContent-Type: text/csv\r\n"
                                f"Content-Disposition: attachment; filename=\"{target_file}\"\r\n\r\n" + csv_content)
                    conn.sendall(http_res.encode('utf-8'))
                except:
                    conn.sendall("HTTP/1.1 404 Not Found\r\n\r\nFile kosong.".encode('utf-8'))

            elif 'GET /esp_update' in req_line:
                parsed = urllib.parse.urlparse(req_line.split(' ')[1])
                params = urllib.parse.parse_qs(parsed.query)
                
                try: alat.suhu_kompor = float(params.get('suhu_kompor', [alat.suhu_kompor])[0])
                except: pass
                try: alat.suhu_ruang = float(params.get('suhu_ruang', [alat.suhu_ruang])[0])
                except: pass
                try: alat.kelembaban = float(params.get('lembab', [alat.kelembaban])[0])
                except: pass
                try: alat.berat_aktual = float(params.get('berat', [alat.berat_aktual])[0])
                except: pass
                
                status_esp = params.get('status', ['RUNNING'])[0]
                fase_esp = params.get('fase_esp', [alat.fase_aktif])[0]
                
                try: 
                    in_sisa = int(params.get('sisa_wkt', [0])[0])
                    if fase_esp == alat.fase_aktif and in_sisa > 0:
                        alat.sisa_waktu_detik = in_sisa
                except: pass
                
                alat.temp_reached = True if params.get('tr', ['0'])[0] == '1' else False
                is_overheat_fan = True if params.get('ovh', ['0'])[0] == '1' else False
                
                if status_esp == "DONE" and alat.fase_aktif != "IDLE":
                    alat.log(f">>> [SELESAI] Fase {alat.fase_aktif} telah tuntas dilakukan ESP32!")
                    alat.fase_aktif = "IDLE" 

                if alat.fase_aktif != "IDLE":
                    try:
                        waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        kategori_gabungan = f"{alat.kategori_lembap}_{alat.kategori_berat}"
                        
                        # LOGIKA MAPPING RELAY 0/1 SEPERTI CONTOH FSM DATA
                        r_chopper = 1 if alat.fase_aktif in ["GRINDING", "TES_GRINDING"] else 0
                        r_heater = 1 if alat.fase_aktif in ["DRYING", "TES_HEATER"] else 0
                        r_pengaduk = 1 if alat.fase_aktif in ["DRYING", "TES_PENGADUK"] else 0
                        r_fan1 = 1 if alat.fase_aktif in ["COOLING", "TES_COOLING"] else 0
                        r_fan2 = 1 if alat.fase_aktif in ["COOLING", "TES_COOLING"] else 0
                        
                        # Fan 3 aktif saat cooling atau overheat
                        r_fan3 = 1 if alat.fase_aktif in ["COOLING", "TES_COOLING"] or (alat.fase_aktif == "DRYING" and is_overheat_fan) else 0
                        
                        # LOGIKA TIMER PEMISAHAN SETPOIN
                        t_grinder = alat.sisa_waktu_detik if alat.fase_aktif == "GRINDING" else 0
                        t_heater = alat.sisa_waktu_detik if alat.fase_aktif == "DRYING" else 0
                        t_cooling = alat.sisa_waktu_detik if alat.fase_aktif == "COOLING" else 0

                        # MENYIMPAN KE CSV MENGGUNAKAN TITIK KOMA (;)
                        with open(csv_utama, "a") as f:
                            f.write(f"{waktu_sekarang};{alat.fase_aktif};{alat.mode_aktif};{kategori_gabungan};{alat.target_suhu};{alat.suhu_kompor};{alat.suhu_ruang};{alat.kelembaban};{alat.berat_aktual};{alat.berat_awal};{alat.berat_akhir};{alat.persentase_susut};{r_heater};{r_chopper};{r_pengaduk};{r_fan1};{r_fan2};{r_fan3};{t_grinder};{t_heater};{t_cooling}\n")
                    except Exception as e: pass
                
                t_wak_kirim = alat.target_waktu
                t_grind_kirim = alat.target_grinding
                
                if status_esp == "BOOT" and alat.fase_aktif != "IDLE":
                    alat.log(f">>> [RECOVERY SYSTEM] ESP32 baru saja Restart. Melanjutkan timer {alat.fase_aktif}...")
                    if alat.fase_aktif == "DRYING" and alat.sisa_waktu_detik > 0:
                        t_wak_kirim = alat.sisa_waktu_detik
                    elif alat.fase_aktif == "GRINDING" and alat.sisa_waktu_detik > 0:
                        t_grind_kirim = alat.sisa_waktu_detik
                    
                response_data = {
                    "fase": alat.fase_aktif,
                    "mode": alat.mode_aktif,
                    "t_suhu": alat.target_suhu,
                    "t_waktu": t_wak_kirim,
                    "t_grinding": t_grind_kirim,
                    "t_aduk": alat.target_pengaduk,
                    "tare": alat.perintah_tare
                }
                alat.perintah_tare = False 
                alat.overheat_fan = is_overheat_fan
                
                res_body = json.dumps(response_data)
                conn.sendall(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{res_body}".encode('utf-8'))

            elif 'GET /data' in req_line:
                res_data = {
                    "suhu_kompor": alat.suhu_kompor, "suhu_ruang": alat.suhu_ruang, 
                    "lembab": alat.kelembaban, "berat": alat.berat_aktual,
                    "fase": alat.fase_aktif, "mode": alat.mode_aktif, "logs": alat.terminal_logs,
                    "sisa_waktu": alat.sisa_waktu_detik, "temp_reached": alat.temp_reached,
                    "overheat_fan": getattr(alat, 'overheat_fan', False)
                }
                conn.sendall(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{json.dumps(res_data)}".encode('utf-8'))
                
            else:
                html_body = html_page.encode('utf-8')
                conn.sendall(f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n".encode('utf-8') + html_body)
            
            conn.close()
        except Exception as e:
            pass 

if __name__ == "__main__":
    start_server()