import importlib
import json
from datetime import date

import pytest


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("MEAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MEAL_REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import app.config as config
    importlib.reload(config)
    import app.db, app.health, app.analysis, app.report, app.reminders, app.server
    for m in (app.db, app.health, app.analysis, app.report, app.reminders, app.server):
        importlib.reload(m)
    return app


def test_vision_parse_json():
    from app.vision import parse_json
    r = parse_json('結果です {"items":[{"name":"ご飯","kind":"food","kcal":"234","protein_g":3.8}],"confidence":"high"}')
    assert r["items"][0]["kcal"] == 234.0 and r["items"][0]["fat_g"] == 0.0


def test_week_analysis_and_report(env, tmp_path):
    import sys
    sys.path.insert(0, "scripts")
    import seed_demo
    end = date(2026, 11, 22)
    seed_demo.seed(end)
    data = env.analysis.analyze_week(end)
    assert len(data["daily"]) == 7
    assert data["summary"]["days_logged"] == 7
    assert data["exercise"]["strength_sessions"] == 3
    assert all(d["net"] is not None for d in data["daily"])
    titles = [n["title"] for n in data["food_notes"] + data["exercise_notes"]]
    assert any("たんぱく質" in t for t in titles)
    path = env.report.build(end)
    html = path.read_text()
    for h in ("1日ごとの総カロリー", "摂取カロリー", "食べたもの・飲んだもの", "よく食べているもの",
              "食事・飲み物についての注意点", "運動内容", "運動についての特徴"):
        assert h in html


def test_health_ingest_and_csv(env):
    n = env.health.ingest({"date": "2026-11-20", "total_burn_kcal": 2400, "steps": 9000, "sleep_hours": 7,
                           "workouts": [{"type": "EXERCISE_TYPE_STRENGTH_TRAINING", "minutes": 50, "muscle_groups": ["legs"]}]})
    assert n == 1
    env.health.import_csv("date,type,name,minutes,sets,muscle_groups\n2026-11-21,weightlifting,胸,45,12,chest;arms\n")
    with env.db.connect() as con:
        h = env.db.health_between(con, "2026-11-20", "2026-11-20")["2026-11-20"]
        assert h["sleep_min"] == 420
        ws = env.db.workouts_between(con, "2026-11-20", "2026-11-21")
    assert [w["type"] for w in ws] == ["strength", "strength"]


def test_server_endpoints(env):
    c = env.server.app.test_client()
    assert c.get("/").status_code == 200
    r = c.post("/api/meals", data={"slot": "朝食", "items": json.dumps([{"name": "卵", "kcal": 80, "protein_g": 6.5}])})
    assert r.status_code == 200
    assert c.post("/api/health", json={"date": "2026-11-23", "total_burn_kcal": 2300}).status_code == 200
    ics = c.get("/reminders.ics").data.decode()
    assert ics.count("BEGIN:VEVENT") == 5 and "RRULE:FREQ=DAILY" in ics and "ACTION:AUDIO" in ics
    assert c.get("/api/push/key").json["publicKey"]
    assert c.get("/report").status_code == 200


def test_gym_workout_adds_to_burn(env):
    with env.db.connect() as con:
        env.health.ingest({"date": "2026-11-24", "total_burn_kcal": 1900}, con)
        env.db.add_workout(con, date="2026-11-24", type="strength", kcal=28, sets=3, add_to_burn=True, ext_id="g1")
        env.db.add_workout(con, date="2026-11-24", type="walking", kcal=100, ext_id="w1")  # ウェアラブル計測分は足さない
        data = env.analysis.analyze_week(date(2026, 11, 24), con)
    assert data["daily"][-1]["burn"] == 1928 and data["daily"][-1]["extra_burn"] == 28
