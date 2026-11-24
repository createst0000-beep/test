"""SQLite ストレージ。食事・健康（消費）データ・運動を保存する。"""
import json
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eaten_at TEXT NOT NULL,          -- ISO8601（ローカル時刻）
    date TEXT NOT NULL,              -- YYYY-MM-DD
    slot TEXT,                       -- 朝食/昼食/夕食/間食・飲み物
    photo TEXT,                      -- data/photos 内のファイル名
    items_json TEXT NOT NULL,        -- [{name, kind(food|drink), amount, kcal, protein_g, fat_g, carb_g, fiber_g, salt_g, alcohol_g}]
    kcal REAL NOT NULL DEFAULT 0,
    protein_g REAL NOT NULL DEFAULT 0,
    fat_g REAL NOT NULL DEFAULT 0,
    carb_g REAL NOT NULL DEFAULT 0,
    fiber_g REAL NOT NULL DEFAULT 0,
    salt_g REAL NOT NULL DEFAULT 0,
    alcohol_g REAL NOT NULL DEFAULT 0,
    confidence TEXT,
    note TEXT
);
CREATE TABLE IF NOT EXISTS daily_health (
    date TEXT PRIMARY KEY,
    total_burn_kcal REAL,            -- 1日の総消費（基礎代謝＋活動）
    active_kcal REAL,                -- 活動による消費
    bmr_kcal REAL,
    steps INTEGER,
    weight_kg REAL,
    body_fat_pct REAL,
    sleep_min REAL,
    resting_hr REAL,
    source TEXT,                     -- health_connect / google_fit / soxai / manual
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL,              -- strength / walking / running / cycling ...
    name TEXT,                       -- 例: ベンチプレス・脚の日
    minutes REAL,
    kcal REAL,
    muscle_groups TEXT,              -- カンマ区切り（chest,back,legs,shoulders,arms,core）
    sets INTEGER,
    source TEXT,
    ext_id TEXT UNIQUE,              -- 取り込み元の ID（重複防止）
    add_to_burn INTEGER DEFAULT 0    -- 1: ウェアラブル未装着の運動。kcal を1日の消費に上乗せする
);
"""


@contextmanager
def connect():
    config.ensure_dirs()
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    try:  # 古いDBへの列追加
        con.execute("ALTER TABLE workouts ADD COLUMN add_to_burn INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        yield con
        con.commit()
    finally:
        con.close()


def add_meal(con, *, eaten_at, slot, photo, items, confidence=None, note=None):
    tot = {k: 0.0 for k in ("kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "salt_g", "alcohol_g")}
    for it in items:
        for k in tot:
            tot[k] += float(it.get(k) or 0)
    cur = con.execute(
        """INSERT INTO meals (eaten_at, date, slot, photo, items_json, kcal, protein_g, fat_g,
           carb_g, fiber_g, salt_g, alcohol_g, confidence, note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (eaten_at, eaten_at[:10], slot, photo, json.dumps(items, ensure_ascii=False),
         tot["kcal"], tot["protein_g"], tot["fat_g"], tot["carb_g"], tot["fiber_g"],
         tot["salt_g"], tot["alcohol_g"], confidence, note),
    )
    return cur.lastrowid


def upsert_health(con, date, source, **fields):
    allowed = {"total_burn_kcal", "active_kcal", "bmr_kcal", "steps", "weight_kg",
               "body_fat_pct", "sleep_min", "resting_hr"}
    fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
    row = con.execute("SELECT * FROM daily_health WHERE date=?", (date,)).fetchone()
    from datetime import datetime
    now = datetime.now(config.TZ).isoformat(timespec="seconds")
    if row is None:
        cols = ["date", "source", "updated_at", *fields]
        con.execute(f"INSERT INTO daily_health ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    (date, source, now, *fields.values()))
    elif fields:
        sets = ",".join(f"{k}=?" for k in fields)
        con.execute(f"UPDATE daily_health SET {sets}, source=?, updated_at=? WHERE date=?",
                    (*fields.values(), source, now, date))


def add_workout(con, *, date, type, name=None, minutes=None, kcal=None,
                muscle_groups=None, sets=None, source="manual", ext_id=None, add_to_burn=False):
    if isinstance(muscle_groups, (list, tuple)):
        muscle_groups = ",".join(muscle_groups)
    con.execute(
        """INSERT OR REPLACE INTO workouts (date, type, name, minutes, kcal, muscle_groups, sets, source, ext_id, add_to_burn)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (date, type, name, minutes, kcal, muscle_groups, sets, source, ext_id, 1 if add_to_burn else 0),
    )


def meals_between(con, start, end):
    return [dict(r) | {"items": json.loads(r["items_json"])} for r in con.execute(
        "SELECT * FROM meals WHERE date BETWEEN ? AND ? ORDER BY eaten_at", (start, end))]


def health_between(con, start, end):
    return {r["date"]: dict(r) for r in con.execute(
        "SELECT * FROM daily_health WHERE date BETWEEN ? AND ? ORDER BY date", (start, end))}


def workouts_between(con, start, end):
    return [dict(r) for r in con.execute(
        "SELECT * FROM workouts WHERE date BETWEEN ? AND ? ORDER BY date", (start, end))]
