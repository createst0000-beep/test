"""Web アプリ本体（スマホのホーム画面に追加して使う PWA）。

起動:  python -m app.server   →  http://<PCやサーバーのIP>:8000
"""
import json
import os
import uuid
from datetime import date, datetime
from functools import wraps

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory

from . import analysis, config, db, health, reminders, report, vision

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
SLOTS = [label for _, _, label in config.REMINDER_TIMES]


def need_token(f):
    """INGEST_TOKEN が設定されていれば Authorization: Bearer <token> を要求する。"""
    @wraps(f)
    def wrap(*a, **k):
        if config.INGEST_TOKEN:
            got = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or request.args.get("token")
            if got != config.INGEST_TOKEN:
                abort(401)
        return f(*a, **k)
    return wrap


def _guess_slot(now):
    h = now.hour
    return "朝食" if h < 10 else "昼食" if h < 15 else "夕食" if h < 20 else "間食・飲み物"


@app.get("/")
def index():
    now = datetime.now(config.TZ)
    slot = request.args.get("slot") or _guess_slot(now)
    with db.connect() as con:
        today = db.meals_between(con, now.date().isoformat(), now.date().isoformat())
        h = db.health_between(con, now.date().isoformat(), now.date().isoformat()).get(now.date().isoformat(), {})
    return render_template("index.html", slots=SLOTS, slot=slot, meals=today, health=h,
                           intake=sum(m["kcal"] for m in today), protein=sum(m["protein_g"] for m in today),
                           protein_target=round(2.0 * config.BODY_WEIGHT_KG), token=config.INGEST_TOKEN and "set")


@app.post("/api/meals")
@need_token
def add_meal():
    now = datetime.now(config.TZ)
    f = request.files.get("photo")
    note = request.form.get("note") or None
    slot = request.form.get("slot") or _guess_slot(now)
    eaten_at = request.form.get("eaten_at") or now.isoformat(timespec="minutes")
    photo_name = None
    result = {"items": [], "confidence": "none", "comment": ""}
    if f and f.filename:
        ext = os.path.splitext(f.filename)[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif"):
            abort(400, "画像ファイルを選んでください")
        photo_name = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{ext}"
        config.ensure_dirs()
        path = config.PHOTO_DIR / photo_name
        f.save(path)
        try:
            result = vision.analyze_photo(path, note)
        except Exception as e:
            result["comment"] = f"自動推定に失敗しました: {e}"
    if request.form.get("items"):
        result["items"] = json.loads(request.form["items"])
    with db.connect() as con:
        mid = db.add_meal(con, eaten_at=eaten_at, slot=slot, photo=photo_name, items=result["items"],
                          confidence=result.get("confidence"), note=note or result.get("comment"))
    return jsonify({"id": mid, **result})


@app.put("/api/meals/<int:mid>")
@need_token
def update_meal(mid):
    """推定結果の手直し（量や品目を修正）。"""
    items = request.get_json()["items"]
    with db.connect() as con:
        row = con.execute("SELECT * FROM meals WHERE id=?", (mid,)).fetchone()
        if not row:
            abort(404)
        con.execute("DELETE FROM meals WHERE id=?", (mid,))
        db.add_meal(con, eaten_at=row["eaten_at"], slot=row["slot"], photo=row["photo"], items=items,
                    confidence="edited", note=row["note"])
    return jsonify({"ok": True})


@app.delete("/api/meals/<int:mid>")
@need_token
def delete_meal(mid):
    with db.connect() as con:
        con.execute("DELETE FROM meals WHERE id=?", (mid,))
    return jsonify({"ok": True})


@app.post("/api/health")
@need_token
def post_health():
    """スマホの自動化アプリ（ヘルスコネクト → HTTP 送信）から日別データを受け取る。"""
    n = health.ingest(request.get_json(force=True))
    return jsonify({"ok": True, "days": n})


@app.post("/api/health/csv")
@need_token
def post_health_csv():
    f = request.files.get("file")
    text = f.read().decode("utf-8-sig") if f else request.get_data(as_text=True)
    return jsonify({"ok": True, "rows": health.import_csv(text)})


@app.post("/api/workouts")
@need_token
def post_workout():
    """筋トレの部位・セット数など、ウェアラブルでは取れない情報を手入力。"""
    w = request.get_json(force=True)
    d = w.get("date") or datetime.now(config.TZ).date().isoformat()
    with db.connect() as con:
        db.add_workout(con, date=d, type=health.normalize_type(w.get("type", "strength")), name=w.get("name"),
                       minutes=w.get("minutes"), kcal=w.get("kcal"), muscle_groups=w.get("muscle_groups"),
                       sets=w.get("sets"), source="manual", ext_id=f"manual:{uuid.uuid4().hex}")
    return jsonify({"ok": True})


@app.get("/report")
def show_report():
    end = request.args.get("end")
    path = report.build(date.fromisoformat(end) if end else None)
    return send_from_directory(path.parent, path.name)


@app.get("/api/week")
def api_week():
    end = request.args.get("end")
    return jsonify(analysis.analyze_week(date.fromisoformat(end) if end else None))


@app.get("/photos/<path:name>")
def photo(name):
    return send_from_directory(config.PHOTO_DIR, name)


@app.get("/reminders.ics")
def ics():
    return Response(reminders.build_ics(request.host_url.rstrip("/")), mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=meal-reminders.ics"})


@app.get("/api/push/key")
def push_key():
    return jsonify({"publicKey": reminders.vapid_keys()["public"]})


@app.post("/api/push/subscribe")
@need_token
def push_subscribe():
    reminders.save_subscription(request.get_json(force=True))
    return jsonify({"ok": True})


@app.post("/api/push/test")
@need_token
def push_test():
    return jsonify({"sent": reminders.send_push("🔔 テスト通知", "音とバイブが鳴れば設定完了です", "/")})


@app.get("/sw.js")
def sw():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


def main():
    from . import scheduler
    config.ensure_dirs()
    if os.environ.get("DISABLE_SCHEDULER") != "1":
        scheduler.start_background()
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
