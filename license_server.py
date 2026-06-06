import os
from datetime import datetime, timezone
from flask import Flask, jsonify, request

app = Flask(__name__)

LICENSES = {
    "DLY-00018": {
        "status": "active",
        "expire": "2026-07-10",
        "pc_id": None
    }
}

def get_server_date():
    return datetime.now(timezone.utc).date()

def parse_expire_date(expire_text):
    return datetime.strptime(expire_text, "%Y-%m-%d").date()

@app.route("/")
def index():
    return jsonify({
        "service": "Dallyo Image Tool License Server",
        "status": "online"
    })

@app.route("/license/<license_id>")
def check_license(license_id):
    pc_id = request.args.get("pc_id","").strip()

    if not pc_id:
        return jsonify({"ok":False,"usable":False,"status":"pc_id_required","expire":"확인불가"})

    lic = LICENSES.get(license_id)
    if not lic:
        return jsonify({"ok":False,"usable":False,"status":"not_found","expire":"확인불가"})

    server_date = get_server_date()
    expire_date = parse_expire_date(lic["expire"])

    if lic["status"] != "active":
        return jsonify({"ok":True,"usable":False,"status":"inactive","expire":lic["expire"]})

    if server_date > expire_date:
        return jsonify({"ok":True,"usable":False,"status":"expired","expire":lic["expire"]})

    if lic["pc_id"] is None:
        lic["pc_id"] = pc_id

    if lic["pc_id"] != pc_id:
        return jsonify({
            "ok":False,
            "usable":False,
            "status":"pc_mismatch",
            "expire":lic["expire"],
            "message":"This license is registered to another PC."
        })

    return jsonify({
        "ok":True,
        "usable":True,
        "status":"active",
        "expire":lic["expire"],
        "license_id":license_id
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT",8000))
    app.run(host="0.0.0.0",port=port)
