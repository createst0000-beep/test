"""消費カロリー・運動・睡眠・体重データの取り込み。

スマホ内のデータの流れ（2026年時点）:
  SOXAI RING ─┐
              ├─> Android ヘルスコネクト（端末内のみ・クラウドAPIなし）──> 自動化アプリ ──> POST /api/health
  Google Fit ─┘
  Google Fit REST API ──> fetch_google_fit()（Google が 2026 年中の終了を予告。動く間の補助手段）
  CSV（ヘルスコネクトのエクスポートアプリ等）──> import_csv()
"""
import csv
import io
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import config, db

# ヘルスコネクト / 各アプリの運動種別 → 内部の種別
TYPE_MAP = {
    "strength_training": "strength", "weightlifting": "strength", "weight_training": "strength",
    "calisthenics": "strength", "筋トレ": "strength", "strength": "strength",
    "walking": "walking", "walk": "walking", "ウォーキング": "walking",
    "running": "running", "run": "running", "treadmill": "running", "ランニング": "running",
    "biking": "cycling", "cycling": "cycling", "biking_stationary": "cycling",
    "swimming_pool": "swimming", "swimming_open_water": "swimming", "swimming": "swimming",
    "high_intensity_interval_training": "hiit", "hiit": "hiit", "yoga": "yoga",
}
# Google Fit の activity type 番号（主要なもののみ）
FIT_ACTIVITY = {1: "cycling", 7: "walking", 8: "running", 80: "strength"}


def normalize_type(t):
    if t is None:
        return "other"
    if isinstance(t, int):
        return FIT_ACTIVITY.get(t, "other")
    key = str(t).lower().replace("exercise_type_", "").replace(" ", "_")
    return TYPE_MAP.get(key, key if key in TYPE_MAP.values() else "other")


def ingest(payload, con=None):
    """JSON（1日分 dict か、そのリスト）を取り込む。

    {"date":"2026-11-23","source":"soxai","total_burn_kcal":2450,"active_kcal":520,"bmr_kcal":1650,
     "steps":9200,"sleep_min":410,"weight_kg":72.4,"body_fat_pct":18.2,"resting_hr":58,
     "workouts":[{"type":"strength","name":"胸・肩","minutes":60,"kcal":280,
                  "muscle_groups":["chest","shoulders"],"sets":16,"id":"hc-xxx"}]}
    """
    if con is None:
        with db.connect() as c:
            return ingest(payload, c)
    days = payload if isinstance(payload, list) else [payload]
    n = 0
    for d in days:
        date = str(d["date"])[:10]
        src = d.get("source", "health_connect")
        if d.get("sleep_hours") and not d.get("sleep_min"):
            d["sleep_min"] = float(d["sleep_hours"]) * 60
        db.upsert_health(con, date, src, **{k: d.get(k) for k in (
            "total_burn_kcal", "active_kcal", "bmr_kcal", "steps", "weight_kg",
            "body_fat_pct", "sleep_min", "resting_hr")})
        for i, w in enumerate(d.get("workouts", [])):
            db.add_workout(con, date=date, type=normalize_type(w.get("type")), name=w.get("name"),
                           minutes=w.get("minutes"), kcal=w.get("kcal"),
                           muscle_groups=w.get("muscle_groups"), sets=w.get("sets"), source=src,
                           ext_id=w.get("id") or f"{src}:{date}:{i}:{w.get('type')}")
        n += 1
    return n


def import_csv(text: str, con=None):
    """列名: date,total_burn_kcal,active_kcal,steps,sleep_min,weight_kg（あるものだけでよい）。
    運動は別 CSV: date,type,name,minutes,kcal,muscle_groups(;区切り),sets"""
    rows = list(csv.DictReader(io.StringIO(text)))
    payload = []
    for r in rows:
        r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k}
        def num(k):
            try:
                return float(r[k]) if r.get(k) not in (None, "") else None
            except ValueError:
                return None
        item = {"date": r["date"], "source": r.get("source") or "csv"}
        if "type" in r:
            item["workouts"] = [{"type": r["type"], "name": r.get("name"), "minutes": num("minutes"),
                                 "kcal": num("kcal"), "sets": int(num("sets")) if num("sets") else None,
                                 "muscle_groups": [g for g in (r.get("muscle_groups") or "").split(";") if g]}]
        for k in ("total_burn_kcal", "active_kcal", "bmr_kcal", "steps", "sleep_min", "weight_kg", "body_fat_pct", "resting_hr"):
            if num(k) is not None:
                item[k] = num(k)
        payload.append(item)
    return ingest(payload, con)


# ------------------------------------------------------------------ Google Fit REST
FIT_TOKEN_FILE = config.DATA_DIR / "google_fit_token.json"
FIT_SCOPES = ("https://www.googleapis.com/auth/fitness.activity.read "
              "https://www.googleapis.com/auth/fitness.body.read "
              "https://www.googleapis.com/auth/fitness.sleep.read")


def _fit_access_token():
    tok = json.loads(FIT_TOKEN_FILE.read_text())
    body = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"], "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", body, timeout=20) as r:
        return json.load(r)["access_token"]


def _fit_post(url, token, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_google_fit(days=7):
    """Google Fit REST API から日別の消費カロリー・歩数・体重とセッション（運動）を取得して保存。
    事前に `python -m app.fit_auth` でリフレッシュトークンを保存しておくこと。"""
    token = _fit_access_token()
    now = datetime.now(config.TZ)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    agg = _fit_post("https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate", token, {
        "aggregateBy": [{"dataTypeName": "com.google.calories.expended"},
                        {"dataTypeName": "com.google.step_count.delta"},
                        {"dataTypeName": "com.google.weight"}],
        "bucketByTime": {"period": {"type": "day", "value": 1, "timeZoneId": str(config.TZ)}},
        "startTimeMillis": int(start.timestamp() * 1000), "endTimeMillis": int(now.timestamp() * 1000)})
    payload = []
    for b in agg.get("bucket", []):
        d = datetime.fromtimestamp(int(b["startTimeMillis"]) / 1000, config.TZ).date().isoformat()
        item = {"date": d, "source": "google_fit"}
        for ds in b["dataset"]:
            pts = ds.get("point", [])
            if not pts:
                continue
            v = pts[-1]["value"][0]
            if "calories" in ds["dataSourceId"]:
                item["total_burn_kcal"] = round(sum(p["value"][0].get("fpVal", 0) for p in pts))
            elif "step_count" in ds["dataSourceId"]:
                item["steps"] = sum(p["value"][0].get("intVal", 0) for p in pts)
            elif "weight" in ds["dataSourceId"]:
                item["weight_kg"] = round(v.get("fpVal", 0), 1)
        payload.append(item)

    q = urllib.parse.urlencode({"startTime": start.isoformat(), "endTime": now.isoformat()})
    req = urllib.request.Request(f"https://www.googleapis.com/fitness/v1/users/me/sessions?{q}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        sessions = json.load(r).get("session", [])
    by_day = {p["date"]: p for p in payload}
    for se in sessions:
        st = datetime.fromtimestamp(int(se["startTimeMillis"]) / 1000, config.TZ)
        minutes = (int(se["endTimeMillis"]) - int(se["startTimeMillis"])) / 60000
        if se.get("activityType") == 72:  # 睡眠
            by_day.setdefault(st.date().isoformat(), {"date": st.date().isoformat(), "source": "google_fit"})
            # 夜に始まった睡眠は翌日の睡眠として扱う
            d = (st + timedelta(hours=12)).date().isoformat()
            by_day.setdefault(d, {"date": d, "source": "google_fit"})
            by_day[d]["sleep_min"] = by_day[d].get("sleep_min", 0) + minutes
            continue
        d = st.date().isoformat()
        by_day.setdefault(d, {"date": d, "source": "google_fit"}).setdefault("workouts", []).append({
            "type": se.get("activityType"), "name": se.get("name"), "minutes": round(minutes), "id": se.get("id")})
    return ingest(list(by_day.values()))
