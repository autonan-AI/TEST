import os
import re
import secrets
import string
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request, redirect, url_for, render_template_string, session

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET_KEY", "CHANGE_ME_ADMIN_SECRET")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1234")


def generate_cd_key():
    alphabet = string.ascii_uppercase + string.digits
    groups = []
    for _ in range(5):
        groups.append("".join(secrets.choice(alphabet) for _ in range(4)))
    return "-".join(groups)


ADMIN_CD_KEY = os.environ.get("ADMIN_CD_KEY", generate_cd_key())

LICENSES = {
    "DLY-000000": {
        "discord_name": "관리자",
        "cd_key": ADMIN_CD_KEY,
        "status": "active",
        "expire": "PERMANENT",
        "pc_id": None,
        "last_seen": None,
        "protected": True
    }
}


def get_server_date():
    return datetime.now(timezone.utc).date()


def parse_expire_date(expire_text):
    return datetime.strptime(expire_text, "%Y-%m-%d").date()


def format_pc_id(pc_id):
    if not pc_id:
        return "미등록"
    pc_id = str(pc_id)
    if len(pc_id) <= 12:
        return pc_id
    return f"{pc_id[:6]}...{pc_id[-6:]}"


def format_cd_key(cd_key):
    if not cd_key:
        return "-"
    cd_key = str(cd_key)
    if len(cd_key) <= 12:
        return cd_key
    return f"{cd_key[:9]}...{cd_key[-6:]}"


def get_next_member_id():
    max_number = 0
    pattern = re.compile(r"^DLY-(\d{6})$")
    for member_id in LICENSES.keys():
        match = pattern.match(member_id)
        if match:
            number = int(match.group(1))
            if number != 0:
                max_number = max(max_number, number)
    return f"DLY-{max_number + 1:06d}"


def find_license_by_cd_key(cd_key):
    for member_id, lic in LICENSES.items():
        if lic.get("cd_key") == cd_key:
            return member_id, lic
    return None, None


@app.route("/")
def index():
    return jsonify({
        "service": "Dallyo Image Tool License Server",
        "status": "online"
    })


@app.route("/license/<cd_key>")
def check_license(cd_key):
    pc_id = request.args.get("pc_id", "").strip()
    cd_key = str(cd_key).strip()

    if not cd_key:
        return jsonify({"ok": False, "usable": False, "status": "cd_key_required", "expire": "확인불가"})

    if not pc_id:
        return jsonify({"ok": False, "usable": False, "status": "pc_id_required", "expire": "확인불가"})

    member_id, lic = find_license_by_cd_key(cd_key)
    if not lic:
        return jsonify({"ok": False, "usable": False, "status": "not_found", "expire": "확인불가"})

    if lic.get("pc_id") is None:
        lic["pc_id"] = pc_id

    lic["last_seen"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if lic.get("pc_id") != pc_id:
        return jsonify({
            "ok": False,
            "usable": False,
            "status": "pc_mismatch",
            "expire": lic.get("expire", "확인불가"),
            "member_id": member_id,
            "message": "This license is registered to another PC."
        })

    if lic.get("status") != "active":
        return jsonify({
            "ok": True,
            "usable": False,
            "status": "inactive",
            "expire": lic.get("expire", "확인불가"),
            "member_id": member_id
        })

    if lic.get("expire") != "PERMANENT":
        server_date = get_server_date()
        expire_date = parse_expire_date(lic["expire"])
        if server_date > expire_date:
            return jsonify({
                "ok": True,
                "usable": False,
                "status": "expired",
                "expire": lic["expire"],
                "member_id": member_id
            })

    return jsonify({
        "ok": True,
        "usable": True,
        "status": "active",
        "expire": lic.get("expire", "확인불가"),
        "member_id": member_id
    })


LOGIN_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>관리자 로그인</title>
<style>
body { font-family: Arial, sans-serif; background:#111; color:#eee; padding:24px; }
input { padding:10px; background:#222; color:#fff; border:1px solid #555; }
button { padding:10px 16px; background:#444; color:#fff; border:0; border-radius:4px; }
.error { color:#ff7070; margin-top:10px; }
</style>
</head>
<body>
<h1>관리자 로그인</h1>
<form method="post">
<input type="password" name="password" placeholder="관리자 비밀번호">
<button type="submit">로그인</button>
</form>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
</body>
</html>
"""


def is_admin_logged_in():
    return session.get("admin_logged_in") is True


def require_admin():
    if not is_admin_logged_in():
        return redirect(url_for("admin_login"))
    return None


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_page"))
        error = "비밀번호가 틀렸습니다."
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


ADMIN_HTML = """
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>달려 이미지툴 라이센스 관리</title>
<style>
body { font-family: Arial, sans-serif; background:#111; color:#eee; padding:24px; }
h1 { margin-bottom:18px; }
table { border-collapse:collapse; width:100%; background:#1b1b1b; }
th, td { border:1px solid #444; padding:10px; text-align:center; }
th { background:#2a2a2a; }
a, button { display:inline-block; margin:2px; padding:7px 10px; color:#fff; background:#444; text-decoration:none; border:0; border-radius:4px; cursor:pointer; }
input { padding:7px; background:#222; color:#fff; border:1px solid #555; width:150px; }
.active { color:#64ff8a; font-weight:bold; }
.inactive { color:#ff7070; font-weight:bold; }
.small { color:#aaa; font-size:13px; margin-bottom:16px; }
.protected { color:#ffd166; font-weight:bold; }
</style>
</head>
<body>
<h1>달려 이미지툴 라이센스 관리</h1>
<div class="small">서버 날짜: {{ server_date }} | <a href="/admin/logout">로그아웃</a></div>
<div style="margin-bottom:14px;">
<a href="/admin/create_member">새 회원 생성</a>
</div>
<table>
<tr>
<th>회원번호</th>
<th>디코이름</th>
<th>CD키</th>
<th>상태</th>
<th>만료일</th>
<th>PC 등록</th>
<th>PC ID</th>
<th>마지막 접속</th>
<th>관리</th>
</tr>
{% for member_id, lic in licenses.items() %}
<tr>
<td class="{{ 'protected' if lic.protected else '' }}">{{ member_id }}</td>
<td>
<form method="post" action="/admin/update_name/{{ member_id }}">
<input name="discord_name" value="{{ lic.discord_name }}">
<button type="submit">저장</button>
</form>
</td>
<td title="{{ lic.cd_key }}">{{ format_cd_key(lic.cd_key) }}</td>
<td class="{{ lic.status }}">{{ lic.status }}</td>
<td>{{ lic.expire }}</td>
<td>{{ "등록됨" if lic.pc_id else "미등록" }}</td>
<td>{{ format_pc_id(lic.pc_id) }}</td>
<td>{{ lic.last_seen if lic.last_seen else "-" }}</td>
<td>
{% if lic.protected %}
보호됨
<a href="/admin/reset_pc/{{ member_id }}">PC 초기화</a>
{% else %}
<a href="/admin/extend/{{ member_id }}/30">30일 연장</a>
<a href="/admin/set_status/{{ member_id }}/active">활성</a>
<a href="/admin/set_status/{{ member_id }}/inactive">비활성</a>
<a href="/admin/reset_pc/{{ member_id }}">PC 초기화</a>
{% endif %}
</td>
</tr>
{% endfor %}
</table>
</body>
</html>
"""


@app.route("/admin")
def admin_page():
    auth = require_admin()
    if auth:
        return auth
    return render_template_string(
        ADMIN_HTML,
        licenses=LICENSES,
        server_date=str(get_server_date()),
        format_pc_id=format_pc_id,
        format_cd_key=format_cd_key
    )


@app.route("/admin/create_member")
def admin_create_member():
    auth = require_admin()
    if auth:
        return auth

    member_id = get_next_member_id()
    cd_key = generate_cd_key()

    while find_license_by_cd_key(cd_key)[1] is not None:
        cd_key = generate_cd_key()

    LICENSES[member_id] = {
        "discord_name": "",
        "cd_key": cd_key,
        "status": "active",
        "expire": (get_server_date() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "pc_id": None,
        "last_seen": None,
        "protected": False
    }

    return redirect(url_for("admin_page"))


@app.route("/admin/update_name/<member_id>", methods=["POST"])
def admin_update_name(member_id):
    auth = require_admin()
    if auth:
        return auth

    lic = LICENSES.get(member_id)
    if not lic:
        return jsonify({"ok": False, "status": "not_found"})

    lic["discord_name"] = request.form.get("discord_name", "").strip()
    return redirect(url_for("admin_page"))


@app.route("/admin/set_status/<member_id>/<status>")
def admin_set_status(member_id, status):
    auth = require_admin()
    if auth:
        return auth

    if status not in ["active", "inactive"]:
        return jsonify({"ok": False, "status": "invalid_status"})

    lic = LICENSES.get(member_id)
    if not lic:
        return jsonify({"ok": False, "status": "not_found"})

    if lic.get("protected"):
        return redirect(url_for("admin_page"))

    lic["status"] = status
    return redirect(url_for("admin_page"))


@app.route("/admin/extend/<member_id>/<int:days>")
def admin_extend_license(member_id, days):
    auth = require_admin()
    if auth:
        return auth

    if days <= 0:
        return jsonify({"ok": False, "status": "invalid_days"})

    lic = LICENSES.get(member_id)
    if not lic:
        return jsonify({"ok": False, "status": "not_found"})

    if lic.get("protected") or lic.get("expire") == "PERMANENT":
        return redirect(url_for("admin_page"))

    today = get_server_date()
    expire_date = parse_expire_date(lic["expire"])
    base_date = expire_date if expire_date > today else today
    lic["expire"] = (base_date + timedelta(days=days)).strftime("%Y-%m-%d")
    return redirect(url_for("admin_page"))


@app.route("/admin/reset_pc/<member_id>")
def reset_pc(member_id):
    auth = require_admin()
    if auth:
        return auth

    lic = LICENSES.get(member_id)
    if not lic:
        return jsonify({"ok": False, "status": "not_found"})

    lic["pc_id"] = None
    lic["last_seen"] = None
    return redirect(url_for("admin_page"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
