import os
from datetime import datetime, timezone
from flask import Flask, jsonify, request

app = Flask(__name__)

# 테스트/초기 운영용 회원 데이터
# expire: YYYY-MM-DD, status: active / inactive
# pc_id: None이면 첫 인증 PC를 자동 등록
LICENSES = {
    "DLY-00018": {
        "status": "active",
        "expire": "2026-07-10",
        "pc_id": None,
    },
    "DLY-00019": {
        "status": "active",
        "expire": "2026-06-05",
        "pc_id": None,
    },
}


def get_server_date():
    return datetime.now(timezone.utc).date()


def parse_expire_date(expire_text):
    return datetime.strptime(expire_text, "%Y-%m-%d").date()


@app.route("/")
def index():
    return jsonify({
        "service": "Dallyo Image Tool License Server",
        "status": "online",
    })


@app.route("/license/<license_id>")
def check_license(license_id):
    pc_id = request.args.get("pc_id", "").strip()

    if not pc_id:
        return jsonify({
            "ok": False,
            "license_id": license_id,
            "status": "pc_id_required",
            "message": "PC ID is required.",
        })

    license_data = LICENSES.get(license_id)
    if license_data is None:
        return jsonify({
            "ok": False,
            "license_id": license_id,
            "status": "not_found",
            "message": "License ID not found.",
        })

    server_date = get_server_date()
    expire_date = parse_expire_date(license_data["expire"])

    if license_data.get("status") != "active":
        return jsonify({
            "ok": True,
            "usable": False,
            "license_id": license_id,
            "status": "inactive",
            "expire": license_data["expire"],
            "server_date": server_date.isoformat(),
        })

    if server_date > expire_date:
        return jsonify({
            "ok": True,
            "usable": False,
            "license_id": license_id,
            "status": "expired",
            "expire": license_data["expire"],
            "server_date": server_date.isoformat(),
        })

    registered_pc_id = license_data.get("pc_id")

    if registered_pc_id is None:
        license_data["pc_id"] = pc_id
        registered_pc_id = pc_id

    if registered_pc_id != pc_id:
        return jsonify({
            "ok": False,
            "usable": False,
            "license_id": license_id,
            "status": "pc_mismatch",
            "message": "This license is registered to another PC.",
            "expire": license_data["expire"],
            "server_date": server_date.isoformat(),
        })

    return jsonify({
        "ok": True,
        "usable": True,
        "license_id": license_id,
        "status": "active",
        "expire": license_data["expire"],
        "server_date": server_date.isoformat(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
