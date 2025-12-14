import requests
import time
import json
import os
import datetime
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify, render_template_string

# ==========================================
# DATA PERSISTENCE (JSON DB)
# ==========================================
app = Flask(__name__)
DB_FILE = "data.json"

# Cấu trúc mặc định
DEFAULT_DB = {
    "users": {
        "ADMINTQ@gmail.com": {"pass": "ADMINTQ", "role": "ADMIN", "limit": 9999, "ticket_limit": 10},
        "SUPER@gmail.com": {"pass": "SUPER", "role": "ADMINISTRATOR", "limit": 9999, "ticket_limit": 99}
    },
    "tickets": [],
    "config": {
        "is_active": True,
        "global_limit": 10
    }
}

def load_db():
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DB)
        return DEFAULT_DB
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "tickets" not in data: data["tickets"] = []
            return data
    except:
        return DEFAULT_DB

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Init DB
DB = load_db()

# ==========================================
# IOE CORE LOGIC (REAL ALGORITHM)
# ==========================================
BASE_URL = "https://api-edu.go.vn/ioe-service/v2/game"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://ioe.vn",
    "Referer": "https://ioe.vn/",
    "Content-Type": "application/json"
}

class IOEBot:
    def parse_token_from_url(self, url):
        try:
            qs = parse_qs(urlparse(url).query)
            return qs.get("token", [None])[0]
        except:
            return None

    def api(self, path, body):
        try:
            res = requests.post(f"{BASE_URL}/{path}", json=body, headers=HEADERS, timeout=10)
            return res.json()
        except:
            return {}

    def try_answer(self, tokenrq, examKey, questId, point, candidate):
        payload = {
            "api_key": "gameioe",
            "serviceCode": "IOE",
            "token": tokenrq,
            "examKey": examKey,
            "ans": {"questId": questId, "point": point, "ans": candidate},
            "IPClient": "127.0.0.1",
            "deviceId": "web-browser"
        }
        jr = self.api("answercheck", payload)
        returned = jr.get("data", {}).get("point", 0)
        return returned == point

    def build_arrange_sentence(self, q):
        tokens = sorted(q.get("ans", []), key=lambda x: x.get("orderTrue", 0))
        return " ".join([t.get("content", "") for t in tokens])

    def build_pairing(self, q):
        text = q.get("content", {}).get("content", "")
        img = q.get("ans", [{}])[0].get("content", "")
        return f"{text}|{img}"

    def build_order_pipe(self, q):
        tokens = sorted(q.get("ans", []), key=lambda x: x.get("orderTrue", 0))
        return "|".join([t.get("content", "") for t in tokens if t.get("content")])

    def prepare_answers(self, ioe_link):
        ioe_token = self.parse_token_from_url(ioe_link)
        if not ioe_token:
            return {"error": "Không tìm thấy token trong URL"}

        getinfo = self.api("getinfo", {
            "IPClient": "",
            "api_key": "gameioe",
            "deviceId": "",
            "serviceCode": "IOE",
            "token": ioe_token
        })

        if not getinfo.get("IsSuccessed"):
            return {"error": "Token hết hạn hoặc lỗi GetInfo"}

        tokenrq = getinfo["data"]["token"]
        examKey = getinfo["data"]["game"]["examKey"]
        questions = getinfo["data"]["game"]["question"]
        qtype = questions[0]["type"]

        # Start game signal
        self.api("startgame", {
            "api_key": "gameioe",
            "serviceCode": "IOE",
            "token": tokenrq,
            "gameId": 0,
            "examKey": examKey,
            "deviceId": "",
            "IPClient": ""
        })

        ans_list = []
        TF = ["True", "False"]

        for q in questions:
            q_id = q["id"]
            q_point = q["Point"]
            final_ans = None

            if qtype == 5:
                final_ans = self.build_arrange_sentence(q)
            elif qtype == 7:
                final_ans = self.build_pairing(q)
            elif qtype == 3:
                final_ans = self.build_order_pipe(q)
            elif qtype in (1, 10):
                options = [x.get("content") for x in q.get("ans", []) if x.get("content")]
                candidates = options if options else TF
                
                for cand in candidates:
                    time.sleep(0.05) # Delay nhẹ tránh spam
                    if self.try_answer(tokenrq, examKey, q_id, q_point, cand):
                        final_ans = cand
                        break
            
            if final_ans:
                ans_list.append({"questId": q_id, "ans": final_ans, "Point": q_point})

        return {
            "token": tokenrq,
            "examKey": examKey,
            "answers": ans_list
        }

    def submit_exam(self, token, examKey, answers):
        fin = self.api("finishgame", {
            "api_key": "gameioe",
            "token": token,
            "serviceCode": "IOE",
            "examKey": examKey,
            "ans": answers,
            "IPClient": "",
            "deviceId": ""
        })
        
        if fin.get("IsSuccessed"):
            return {"success": True, "score": fin.get("data", {}).get("totalPoint", "???")}
        return {"success": False, "msg": fin.get("msg", "Lỗi không xác định")}

# ==========================================
# GIAO DIỆN HTML (V10.1)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IOE PRO V10.1</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons+Round" rel="stylesheet">
    <style>
        :root {
            --bg-grad: linear-gradient(135deg, #0f172a, #1e293b);
            --glass: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --sidebar-bg: rgba(0, 0, 0, 0.4);
            --primary: #6366f1;
            --accent: #06b6d4;
            --text: #f8fafc;
            --text-dim: #94a3b8;
            --danger: #ef4444;
            --success: #10b981;
            --warning: #f59e0b;
            --admin-color: #8b5cf6;
            --super-color: #f43f5e;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }

        body {
            background: var(--bg-grad);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text);
            overflow: hidden;
        }

        /* Background */
        .blob { position: absolute; border-radius: 50%; filter: blur(100px); z-index: -1; opacity: 0.3; }
        .blob-1 { top: -10%; left: -10%; width: 600px; height: 600px; background: var(--primary); }
        .blob-2 { bottom: -10%; right: -10%; width: 500px; height: 500px; background: var(--super-color); }

        /* Layout */
        .container { width: 100vw; height: 100vh; display: flex; }
        
        /* Sidebar */
        .sidebar {
            width: 280px;
            background: var(--sidebar-bg);
            border-right: 1px solid var(--glass-border);
            display: flex; flex-direction: column; padding: 24px;
            backdrop-filter: blur(10px);
        }
        .logo { font-size: 24px; font-weight: 900; color: #fff; margin-bottom: 32px; display: flex; align-items: center; gap: 10px; }
        .logo span { color: var(--accent); }
        
        .nav-item {
            display: flex; align-items: center; gap: 12px; padding: 12px 16px;
            margin-bottom: 4px; border-radius: 12px; cursor: pointer;
            color: var(--text-dim); transition: 0.2s; font-weight: 500;
        }
        .nav-item:hover { background: rgba(255,255,255,0.05); color: #fff; }
        .nav-item.active { background: var(--primary); color: #fff; box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3); }
        
        .nav-label { font-size: 11px; text-transform: uppercase; color: var(--text-dim); font-weight: 700; margin: 24px 0 8px 12px; }

        .user-profile { margin-top: auto; padding-top: 20px; border-top: 1px solid var(--glass-border); display: flex; align-items: center; gap: 12px; }
        .avatar { width: 40px; height: 40px; border-radius: 10px; background: var(--primary); display: flex; justify-content: center; align-items: center; font-weight: bold; }
        
        /* Main */
        .main { flex: 1; padding: 32px; overflow-y: auto; position: relative; }
        .page-header { margin-bottom: 24px; }
        .page-title { font-size: 28px; font-weight: 800; }
        
        /* Panels */
        .panel { background: var(--glass); border: 1px solid var(--glass-border); border-radius: 20px; padding: 24px; margin-bottom: 24px; }
        
        /* STATS GRID */
        .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-box { background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); padding: 20px; border-radius: 16px; text-align: center; }
        .stat-num { font-size: 24px; font-weight: 800; color: var(--accent); display: block; margin-bottom: 4px; }
        .stat-desc { font-size: 11px; color: var(--text-dim); text-transform: uppercase; font-weight: 700; }

        /* Inputs & Buttons */
        .input-group { margin-bottom: 16px; }
        label { display: block; font-size: 12px; color: var(--text-dim); margin-bottom: 6px; font-weight: 600; }
        input, select, textarea {
            width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--glass-border);
            padding: 12px 16px; border-radius: 12px; color: #fff; font-size: 14px; outline: none; transition: 0.2s;
        }
        textarea { resize: vertical; min-height: 100px; }
        input:focus, textarea:focus { border-color: var(--primary); background: rgba(0,0,0,0.5); }

        .btn {
            padding: 12px 24px; border: none; border-radius: 12px;
            background: var(--primary); color: #fff; font-weight: 600; cursor: pointer; transition: 0.2s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(99, 102, 241, 0.4); }
        .btn-danger { background: var(--danger); }
        .btn-success { background: var(--success); }

        /* Ticket Styles */
        .ticket-card {
            background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border);
            border-radius: 12px; padding: 16px; margin-bottom: 12px;
            display: flex; justify-content: space-between; align-items: center;
        }
        .ticket-info h4 { font-size: 14px; color: #fff; margin-bottom: 4px; }
        .ticket-info p { font-size: 13px; color: var(--text-dim); }
        .ticket-status { font-size: 11px; padding: 4px 8px; border-radius: 6px; background: rgba(255,255,255,0.1); }
        .status-open { color: var(--warning); background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); }
        .status-closed { color: var(--success); background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); }

        /* Table */
        .data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
        .data-table th { text-align: left; padding: 12px; color: var(--text-dim); border-bottom: 1px solid var(--glass-border); }
        .data-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); }
        
        /* Modals */
        .modal {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); backdrop-filter: blur(8px);
            display: flex; justify-content: center; align-items: center;
            z-index: 100; opacity: 0; pointer-events: none; transition: 0.3s;
        }
        .modal.open { opacity: 1; pointer-events: all; }
        .modal-content { background: #1e293b; padding: 32px; border-radius: 24px; width: 400px; border: 1px solid var(--glass-border); }

        /* Auth Screen */
        #auth-screen { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 50; background: var(--bg-grad); display: flex; justify-content: center; align-items: center; }
        .auth-box { width: 380px; background: var(--glass); backdrop-filter: blur(20px); padding: 40px; border-radius: 24px; border: 1px solid var(--glass-border); }

        .badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700; }
        .b-admin { background: var(--admin-color); color: #fff; }
        .b-super { background: var(--super-color); color: #fff; }
        .b-mem { background: rgba(255,255,255,0.1); color: var(--text-dim); }

        .hidden { display: none !important; }
    </style>
</head>
<body>

    <div class="blob blob-1"></div>
    <div class="blob blob-2"></div>

    <!-- === AUTH SCREEN === -->
    <div id="auth-screen">
        <div class="auth-box">
            <h1 style="text-align:center; margin-bottom: 8px;">IOE PRO V10</h1>
            <p style="text-align:center; color:var(--text-dim); margin-bottom: 24px; font-size:13px">Hệ thống quản lý & Hỗ trợ</p>
            
            <div id="form-login">
                <div class="input-group"><label>Email</label><input type="email" id="l-email"></div>
                <div class="input-group"><label>Password</label><input type="password" id="l-pass"></div>
                <button class="btn" style="width:100%" onclick="doLogin()">Đăng Nhập</button>
                <div style="text-align:center; margin-top:16px; font-size:13px; cursor:pointer; color:var(--accent)" onclick="toggleAuth()">Chưa có tài khoản? Đăng Ký</div>
            </div>

            <div id="form-register" class="hidden">
                <div class="input-group"><label>New Email</label><input type="email" id="r-email"></div>
                <div class="input-group"><label>New Password</label><input type="password" id="r-pass"></div>
                <button class="btn" style="width:100%" onclick="doRegister()">Tạo Tài Khoản</button>
                <div style="text-align:center; margin-top:16px; font-size:13px; cursor:pointer; color:var(--accent)" onclick="toggleAuth()">Quay lại Đăng Nhập</div>
            </div>
        </div>
    </div>

    <!-- === APP SCREEN === -->
    <div class="container hidden" id="app-screen">
        
        <!-- SIDEBAR -->
        <div class="sidebar">
            <div class="logo"><span class="material-icons-round">rocket_launch</span> IOE<span>V10</span></div>
            
            <div class="nav-item active" onclick="navTo('page-dash', this)">
                <span class="material-icons-round">dashboard</span> Dashboard
            </div>
            <div class="nav-item" onclick="navTo('page-support', this)">
                <span class="material-icons-round">confirmation_number</span> Gửi Hỗ Trợ
            </div>

            <!-- ADMIN SECTION -->
            <div id="admin-menu" class="hidden">
                <div class="nav-label">Quản Trị Viên</div>
                <div class="nav-item" onclick="navTo('page-users', this)">
                    <span class="material-icons-round">people</span> Quản Lý User
                </div>
                <div class="nav-item" onclick="navTo('page-inbox', this)">
                    <span class="material-icons-round">inbox</span> Hộp Thư <span id="inbox-count" style="margin-left:auto; font-size:10px; background:var(--danger); padding:2px 6px; border-radius:10px; color:#fff">0</span>
                </div>
                <div class="nav-item" onclick="navTo('page-server', this)">
                    <span class="material-icons-round">dns</span> Server
                </div>
            </div>

            <!-- SUPER ADMIN SECTION -->
            <div id="super-menu" class="hidden">
                <div class="nav-label" style="color:var(--super-color)">Administrator</div>
                <div class="nav-item" onclick="navTo('page-upgrade', this)">
                    <span class="material-icons-round">upgrade</span> Nâng Cấp Bản Thân
                </div>
            </div>

            <div class="user-profile">
                <div class="avatar" id="u-avt">U</div>
                <div>
                    <div style="font-size:13px; font-weight:700" id="u-email">User</div>
                    <div style="font-size:10px; color:var(--text-dim)" id="u-role">MEMBER</div>
                </div>
                <span class="material-icons-round" style="margin-left:auto; cursor:pointer; color:var(--danger)" onclick="doLogout()">logout</span>
            </div>
        </div>

        <!-- MAIN CONTENT -->
        <div class="main">
            
            <!-- 1. DASHBOARD -->
            <div id="page-dash" class="section">
                <div class="page-header"><div class="page-title">Dashboard</div></div>
                
                <!-- STATS GRID -->
                <div class="grid-3">
                    <div class="stat-box">
                        <span class="stat-num" id="stat-limit">--/--</span>
                        <span class="stat-desc">Lượt dùng hôm nay</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-num" style="color: var(--success)" id="stat-server">ONLINE</span>
                        <span class="stat-desc">Trạng thái Server</span>
                    </div>
                    <div class="stat-box">
                        <span class="stat-num" style="color: var(--primary)">V10.1</span>
                        <span class="stat-desc">Phiên bản</span>
                    </div>
                </div>

                <div class="panel">
                    <div class="input-group"><label>Link IOE</label><input type="text" id="ioe-link" placeholder="https://ioe.vn/lam-bai/..."></div>
                    <div class="input-group"><label>Delay (giây)</label><input type="number" id="ioe-delay" value="15"></div>
                    <button class="btn" id="btn-run" onclick="runTool()">CHẠY NGAY</button>
                    <div id="run-log" style="margin-top:20px; font-family:monospace; font-size:13px; color:var(--accent); min-height:40px;"></div>
                </div>
            </div>

            <!-- 2. SUPPORT (USER) -->
            <div id="page-support" class="section hidden">
                <div class="page-header"><div class="page-title">Hỗ Trợ Kỹ Thuật</div></div>
                <div class="panel">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                        <span>Ticket của bạn: <b id="my-ticket-count">0</b> / <b id="my-ticket-limit">2</b></span>
                        <button class="btn" onclick="sendTicket()">Gửi Ticket Mới</button>
                    </div>
                    <textarea id="ticket-content" placeholder="Mô tả vấn đề của bạn..."></textarea>
                </div>
                <h3>Lịch sử Ticket</h3>
                <div id="my-ticket-list" style="margin-top:16px;"></div>
            </div>

            <!-- 3. USER MANAGER (ADMIN) -->
            <div id="page-users" class="section hidden">
                <div class="page-header"><div class="page-title">Quản Lý Người Dùng</div></div>
                <div class="panel">
                    <table class="data-table">
                        <thead><tr><th>Email</th><th>Role</th><th>Limit Run</th><th>Limit Ticket</th><th>Action</th></tr></thead>
                        <tbody id="user-table-body"></tbody>
                    </table>
                </div>
            </div>

            <!-- 4. INBOX (ADMIN/SUPER) -->
            <div id="page-inbox" class="section hidden">
                <div class="page-header">
                    <div class="page-title">Hộp Thư Hỗ Trợ</div>
                    <p style="font-size:13px; color:var(--text-dim)">
                        <span id="inbox-status">Hệ thống hoạt động bình thường.</span>
                    </p>
                </div>
                <div id="admin-ticket-list"></div>
            </div>

            <!-- 5. SERVER (ADMIN) -->
            <div id="page-server" class="section hidden">
                <div class="page-header"><div class="page-title">Cấu Hình Server</div></div>
                <div class="panel">
                    <div class="input-group"><label>Global Limit (Lượt chạy)</label><input type="number" id="cfg-limit"></div>
                    <button class="btn" onclick="saveConfig()">Lưu Cấu Hình</button>
                    <hr style="border:0; border-top:1px solid var(--glass-border); margin:20px 0">
                    <button class="btn btn-danger" onclick="toggleServer()">BẬT / TẮT SERVER</button>
                </div>
            </div>

            <!-- 6. SELF UPGRADE (ADMINISTRATOR ONLY) -->
            <div id="page-upgrade" class="section hidden">
                <div class="page-header"><div class="page-title" style="color:var(--super-color)">Administrator Control</div></div>
                <div class="panel" style="border-color:var(--super-color)">
                    <h3>Nâng Cấp Lượt Chạy Cho Mình</h3>
                    <p style="margin-bottom:20px; font-size:13px; color:var(--text-dim)">Quyền hạn đặc biệt của Administrator.</p>
                    <div class="input-group"><label>Số lượt muốn set</label><input type="number" id="super-limit" placeholder="VD: 9999"></div>
                    <button class="btn" style="background:var(--super-color)" onclick="superUpgrade()">Nâng Cấp Ngay</button>
                </div>
            </div>

        </div>
    </div>

    <!-- MODAL EDIT USER -->
    <div id="modal-edit" class="modal">
        <div class="modal-content">
            <h3 style="margin-bottom:20px">Chỉnh Sửa User</h3>
            <input type="hidden" id="edit-origin-email">
            <div class="input-group"><label>Email</label><input type="text" id="edit-email" readonly></div>
            <div class="input-group"><label>New Pass</label><input type="text" id="edit-pass" placeholder="(Không đổi thì để trống)"></div>
            <div class="input-group"><label>Role</label>
                <select id="edit-role">
                    <option value="MEMBER">MEMBER</option>
                    <option value="ADMIN">ADMIN</option>
                    <option value="ADMINISTRATOR">ADMINISTRATOR</option>
                </select>
            </div>
            <div style="display:flex; gap:10px">
                <div class="input-group"><label>Run Limit</label><input type="number" id="edit-run-limit"></div>
                <div class="input-group"><label>Ticket Limit</label><input type="number" id="edit-ticket-limit"></div>
            </div>
            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:20px">
                <button class="btn" style="background:transparent; border:1px solid var(--glass-border)" onclick="closeModal()">Hủy</button>
                <button class="btn" onclick="saveUser()">Lưu</button>
            </div>
        </div>
    </div>

    <script>
        // --- GLOBAL ---
        let ME = null;

        // --- AUTH ---
        function toggleAuth() {
            document.getElementById('form-login').classList.toggle('hidden');
            document.getElementById('form-register').classList.toggle('hidden');
        }

        async function doLogin() {
            const e = document.getElementById('l-email').value;
            const p = document.getElementById('l-pass').value;
            const res = await fetch('/api/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:e, pass:p}) });
            const d = await res.json();
            if(d.success) initApp(d.user); else alert(d.msg);
        }

        async function doRegister() {
            const e = document.getElementById('r-email').value;
            const p = document.getElementById('r-pass').value;
            const res = await fetch('/api/auth/register', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:e, pass:p}) });
            const d = await res.json();
            alert(d.msg); if(d.success) toggleAuth();
        }

        function doLogout() {
            location.reload();
        }

        // --- APP INIT ---
        function initApp(user) {
            ME = user;
            document.getElementById('auth-screen').classList.add('hidden');
            document.getElementById('app-screen').classList.remove('hidden');
            
            document.getElementById('u-email').innerText = user.email.split('@')[0];
            document.getElementById('u-role').innerText = user.role;
            document.getElementById('u-avt').innerText = user.email[0].toUpperCase();

            if(user.role === 'ADMIN' || user.role === 'ADMINISTRATOR') {
                document.getElementById('admin-menu').classList.remove('hidden');
            }
            if(user.role === 'ADMINISTRATOR') {
                document.getElementById('super-menu').classList.remove('hidden');
            }

            navTo('page-dash', document.querySelector('.nav-item')); 
            loadMyTickets();
            fetchStatus(); // Fetch Stats Immediately
        }

        function navTo(pid, el) {
            document.querySelectorAll('.section').forEach(x => x.classList.add('hidden'));
            document.getElementById(pid).classList.remove('hidden');
            
            document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
            el.classList.add('active');

            if(pid === 'page-users') loadUsers();
            if(pid === 'page-inbox') loadInbox();
            if(pid === 'page-server') loadConfig();
            if(pid === 'page-dash') fetchStatus(); // Fetch Stats on Tab Switch
        }

        // --- STATUS LOGIC (NEW) ---
        async function fetchStatus() {
            if(!ME) return;
            const res = await fetch('/api/status?email=' + ME.email);
            const data = await res.json();

            // Update Server Status
            document.getElementById('stat-server').innerText = data.server_active ? "ONLINE" : "BẢO TRÌ";
            document.getElementById('stat-server').style.color = data.server_active ? "var(--success)" : "var(--danger)";

            // Update Count
            const today = new Date().toDateString();
            let local = JSON.parse(localStorage.getItem('ioe_count_v10') || '{}');
            if(local.date !== today) local = { date: today, count: 0 };

            document.getElementById('stat-limit').innerText = `${local.count} / ${data.my_limit}`;
            
            // Lock Button if limit reached
            const btn = document.getElementById('btn-run');
            if(local.count >= data.my_limit) {
                btn.disabled = true; btn.innerText = "HẾT LƯỢT";
            }
        }

        // --- TICKET SYSTEM ---
        async function loadMyTickets() {
            const res = await fetch('/api/ticket/list?email='+ME.email);
            const d = await res.json();
            document.getElementById('my-ticket-count').innerText = d.count;
            document.getElementById('my-ticket-limit').innerText = d.limit;
            
            const div = document.getElementById('my-ticket-list');
            div.innerHTML = d.tickets.map(t => `
                <div class="ticket-card">
                    <div class="ticket-info">
                        <h4>${t.content}</h4>
                        <p>${new Date(t.time * 1000).toLocaleString()}</p>
                    </div>
                    <div class="ticket-status ${t.status=='open'?'status-open':'status-closed'}">${t.status}</div>
                </div>
            `).join('');
        }

        async function sendTicket() {
            const content = document.getElementById('ticket-content').value;
            if(!content) return alert("Viết gì đó đi!");
            const res = await fetch('/api/ticket/send', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:ME.email, content}) });
            const d = await res.json();
            if(d.success) {
                document.getElementById('ticket-content').value = "";
                loadMyTickets();
            } else {
                alert(d.msg);
            }
        }

        async function loadInbox() {
            const res = await fetch('/api/admin/tickets?email='+ME.email);
            const d = await res.json();
            
            const count = d.tickets.length;
            document.getElementById('inbox-count').innerText = count;
            const statusEl = document.getElementById('inbox-status');
            
            if (count > 100) {
                statusEl.innerHTML = `<span style="color:var(--super-color); font-weight:bold">QUÁ TẢI (${count})!</span> Đang chuyển tiếp cho ADMINISTRATOR xử lý.`;
            } else {
                statusEl.innerText = "Hệ thống ổn định.";
            }

            const div = document.getElementById('admin-ticket-list');
            div.innerHTML = d.tickets.map(t => `
                <div class="ticket-card">
                    <div class="ticket-info">
                        <p style="color:var(--accent); font-size:11px; font-weight:bold">${t.email}</p>
                        <h4>${t.content}</h4>
                        <p>${new Date(t.time * 1000).toLocaleString()}</p>
                    </div>
                    <button class="btn btn-success" style="padding:6px 12px; font-size:12px" onclick="closeTicket(${t.id})">Đã Xử Lý</button>
                </div>
            `).join('');
        }

        async function closeTicket(tid) {
            await fetch('/api/admin/ticket/close', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id: tid}) });
            loadInbox();
        }

        // --- USER MANAGEMENT ---
        async function loadUsers() {
            const res = await fetch('/api/admin/users');
            const list = await res.json();
            const tbody = document.getElementById('user-table-body');
            tbody.innerHTML = list.map(u => `
                <tr>
                    <td>${u.email}</td>
                    <td><span class="badge ${u.role=='ADMIN'?'b-admin':(u.role=='ADMINISTRATOR'?'b-super':'b-mem')}">${u.role}</span></td>
                    <td>${u.limit}</td>
                    <td>${u.ticket_limit}</td>
                    <td>
                        <button onclick="openEdit('${u.email}')" style="background:none; border:none; color:var(--accent); cursor:pointer"><span class="material-icons-round" style="font-size:18px">edit</span></button>
                        <button onclick="delUser('${u.email}')" style="background:none; border:none; color:var(--danger); cursor:pointer"><span class="material-icons-round" style="font-size:18px">delete</span></button>
                    </td>
                </tr>
            `).join('');
        }

        async function openEdit(email) {
            const res = await fetch('/api/user/info?email='+email);
            const u = await res.json();
            document.getElementById('edit-origin-email').value = email;
            document.getElementById('edit-email').value = email;
            document.getElementById('edit-role').value = u.role;
            document.getElementById('edit-run-limit').value = u.limit;
            document.getElementById('edit-ticket-limit').value = u.ticket_limit;
            document.getElementById('modal-edit').classList.add('open');
        }

        function closeModal() { document.getElementById('modal-edit').classList.remove('open'); }

        async function saveUser() {
            const email = document.getElementById('edit-origin-email').value;
            const role = document.getElementById('edit-role').value;
            const limit = parseInt(document.getElementById('edit-run-limit').value);
            const t_limit = parseInt(document.getElementById('edit-ticket-limit').value);
            const pass = document.getElementById('edit-pass').value;
            
            await fetch('/api/admin/user/edit', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body:JSON.stringify({email, role, limit, ticket_limit:t_limit, pass})
            });
            closeModal();
            loadUsers();
        }

        async function delUser(email) {
            if(confirm("Xóa user này?")) {
                await fetch('/api/admin/user/del', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email}) });
                loadUsers();
            }
        }

        // --- SUPER ADMIN ---
        async function superUpgrade() {
            const val = document.getElementById('super-limit').value;
            await fetch('/api/super/upgrade', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:ME.email, limit: parseInt(val)}) });
            alert("Đã nâng cấp sức mạnh!");
            fetchStatus();
        }

        // --- SERVER CONFIG ---
        async function loadConfig() {
            // Simulated
        }
        async function saveConfig() {
            const val = document.getElementById('cfg-limit').value;
            await fetch('/api/admin/config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'limit', value:val}) });
            alert("Saved!");
        }
        async function toggleServer() {
            await fetch('/api/admin/config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'toggle'}) });
            alert("Đã đổi trạng thái Server");
            fetchStatus();
        }

        // --- RUN TOOL ---
        async function runTool() {
            const link = document.getElementById('ioe-link').value;
            const delay = document.getElementById('ioe-delay').value;
            const log = document.getElementById('run-log');
            const btn = document.getElementById('btn-run');
            
            // Check Limit Logic
            const today = new Date().toDateString();
            let local = JSON.parse(localStorage.getItem('ioe_count_v10') || '{}');
            if(local.date !== today) local = { date: today, count: 0 };
            
            // Lấy limit từ UI (đã sync) hoặc mặc định
            const currentLimitText = document.getElementById('stat-limit').innerText.split('/')[1] || "10";
            const maxLimit = parseInt(currentLimitText);

            if(local.count >= maxLimit) return alert("Hết lượt!");

            if(!link) return alert("Nhập link đi!");
            
            btn.disabled = true; btn.innerText = "ĐANG CHẠY...";
            log.innerText = "🚀 Đang kết nối hệ thống...";
            
            try {
                const sRes = await fetch('/api/start', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({link}) });
                const sData = await sRes.json();
                
                if(sData.error) { log.innerText = "❌ Lỗi: " + sData.error; btn.disabled=false; btn.innerText="CHẠY NGAY"; return; }
                
                // Increment
                local.count++;
                localStorage.setItem('ioe_count_v10', JSON.stringify(local));
                fetchStatus(); // Update UI

                log.innerText = `✅ Giải xong. Đợi ${delay}s nộp bài...`;
                await new Promise(r => setTimeout(r, delay*1000));
                
                const fRes = await fetch('/api/submit', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:sData.token, examKey:sData.examKey, answers:sData.answers}) });
                const fData = await fRes.json();
                
                if(fData.success) log.innerText = `🏆 HOÀN THÀNH! Điểm: ${fData.score}`;
                else log.innerText = "❌ Nộp thất bại: " + (fData.msg || "");
                
            } catch(e) { log.innerText = "❌ Lỗi mạng."; }
            finally { btn.disabled = false; btn.innerText = "CHẠY NGAY"; }
        }

    </script>
</body>
</html>
"""

# ==========================================
# BACKEND ROUTES
# ==========================================

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

# --- AUTH ---
@app.route("/api/auth/login", methods=["POST"])
def login():
    d = request.json
    u = DB["users"].get(d["email"])
    if u and u["pass"] == d["pass"]:
        return jsonify({"success": True, "user": {"email": d["email"], **u}})
    return jsonify({"success": False, "msg": "Sai tài khoản/mật khẩu"})

@app.route("/api/auth/register", methods=["POST"])
def register():
    d = request.json
    if d["email"] in DB["users"]: return jsonify({"success": False, "msg": "Email tồn tại"})
    DB["users"][d["email"]] = {"pass": d["pass"], "role": "MEMBER", "limit": 10, "ticket_limit": 2}
    save_db(DB)
    return jsonify({"success": True, "msg": "Đăng ký thành công"})

@app.route("/api/user/info", methods=["GET"])
def user_info():
    e = request.args.get("email")
    u = DB["users"].get(e)
    return jsonify({"email": e, **u} if u else {})

# --- STATUS API ---
@app.route("/api/status", methods=["GET"])
def get_status():
    email = request.args.get("email")
    my_limit = DB["config"]["global_limit"]
    
    if email and email in DB["users"]:
        user_limit = DB["users"][email].get("limit")
        if user_limit is not None: my_limit = user_limit

    return jsonify({
        "server_active": DB["config"]["is_active"],
        "my_limit": my_limit
    })

# --- TICKET SYSTEM ---
@app.route("/api/ticket/send", methods=["POST"])
def send_ticket():
    d = request.json
    email = d["email"]
    user = DB["users"].get(email)
    
    # Check limit
    my_tickets = [t for t in DB["tickets"] if t["email"] == email and t["status"] == "open"]
    if len(my_tickets) >= user.get("ticket_limit", 2):
        return jsonify({"success": False, "msg": "Bạn đã hết lượt gửi Ticket (Đang chờ xử lý)."})
    
    ticket = {
        "id": int(time.time()*1000),
        "email": email,
        "content": d["content"],
        "status": "open",
        "time": time.time()
    }
    DB["tickets"].append(ticket)
    save_db(DB)
    return jsonify({"success": True})

@app.route("/api/ticket/list", methods=["GET"])
def list_my_tickets():
    email = request.args.get("email")
    user = DB["users"].get(email)
    user_tickets = [t for t in DB["tickets"] if t["email"] == email]
    # Sort new first
    user_tickets.sort(key=lambda x: x["time"], reverse=True)
    
    return jsonify({
        "count": len([t for t in user_tickets if t["status"] == "open"]),
        "limit": user.get("ticket_limit", 2),
        "tickets": user_tickets
    })

@app.route("/api/admin/tickets", methods=["GET"])
def list_all_tickets():
    req_email = request.args.get("email")
    user = DB["users"].get(req_email)
    
    all_open = [t for t in DB["tickets"] if t["status"] == "open"]
    
    # Logic Overflow: > 100 tickets -> ADMINISTRATOR can see
    is_super = user["role"] == "ADMINISTRATOR"
    is_admin = user["role"] == "ADMIN"
    
    if not (is_admin or is_super): return jsonify({"tickets": []})
    
    all_open.sort(key=lambda x: x["time"], reverse=True)
    return jsonify({"tickets": all_open})

@app.route("/api/admin/ticket/close", methods=["POST"])
def close_ticket():
    tid = request.json.get("id")
    for t in DB["tickets"]:
        if t["id"] == tid:
            t["status"] = "closed"
            break
    save_db(DB)
    return jsonify({"success": True})

# --- ADMIN USER MANAGEMENT ---
@app.route("/api/admin/users", methods=["GET"])
def list_users():
    lst = []
    for k, v in DB["users"].items():
        lst.append({"email": k, **v})
    return jsonify(lst)

@app.route("/api/admin/user/edit", methods=["POST"])
def edit_user():
    d = request.json
    e = d["email"]
    if e in DB["users"]:
        DB["users"][e]["role"] = d["role"]
        DB["users"][e]["limit"] = d["limit"]
        DB["users"][e]["ticket_limit"] = d["ticket_limit"]
        if d.get("pass"): DB["users"][e]["pass"] = d["pass"]
        save_db(DB)
    return jsonify({"success": True})

@app.route("/api/admin/user/del", methods=["POST"])
def del_user():
    e = request.json.get("email")
    if e in DB["users"]:
        del DB["users"][e]
        save_db(DB)
    return jsonify({"success": True})

# --- CONFIG & SUPER ---
@app.route("/api/admin/config", methods=["POST"])
def cfg():
    d = request.json
    if d["action"] == "limit": DB["config"]["global_limit"] = int(d["value"])
    if d["action"] == "toggle": DB["config"]["is_active"] = not DB["config"]["is_active"]
    save_db(DB)
    return jsonify({"success": True})

@app.route("/api/super/upgrade", methods=["POST"])
def super_up():
    d = request.json
    e = d["email"]
    if e in DB["users"] and DB["users"][e]["role"] == "ADMINISTRATOR":
        DB["users"][e]["limit"] = int(d["limit"])
        save_db(DB)
        return jsonify({"success": True})
    return jsonify({"success": False})

# --- TOOL LOGIC (REAL) ---
@app.route("/api/start", methods=["POST"])
def start_game():
    if not DB["config"]["is_active"]: return jsonify({"error": "Server Bảo Trì"})
    
    link = request.json.get("link")
    bot = IOEBot()
    result = bot.prepare_answers(link)
    return jsonify(result)

@app.route("/api/submit", methods=["POST"])
def sub_game():
    d = request.json
    bot = IOEBot()
    result = bot.submit_exam(d.get("token"), d.get("examKey"), d.get("answers"))
    return jsonify(result)

if __name__ == "__main__":
    app.run(port=5000, debug=False)
# root@1406851707962392626:~# 
