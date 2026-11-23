"""動作確認用のサンプル1週間分を投入する。  MEAL_DATA_DIR=/tmp/demo python scripts/seed_demo.py"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db, health  # noqa: E402

F = lambda name, kcal, p, f, c, fib=0, salt=0, kind="food", amount="", alc=0, upf=False: {
    "name": name, "kind": kind, "amount": amount, "kcal": kcal, "protein_g": p, "fat_g": f, "carb_g": c,
    "fiber_g": fib, "salt_g": salt, "alcohol_g": alc, "ultra_processed": upf}

BREAKFAST = [
    [F("ご飯", 234, 3.8, 0.5, 55.7, 2.3, 0, amount="150g"), F("納豆", 90, 7.4, 4.5, 5.4, 3, 0.6), F("味噌汁", 40, 2.5, 1.2, 4, 1, 1.5)],
    [F("食パン（6枚切り）", 149, 5.3, 2.5, 27.8, 2.5, 0.7, upf=True), F("ゆで卵", 76, 6.5, 5.1, 0.2, 0, 0.2, amount="1個"), F("カフェラテ", 120, 6, 6, 9, kind="drink", amount="M")],
    [F("ギリシャヨーグルト", 90, 10, 0, 12, 0, 0.1), F("バナナ", 86, 1.1, 0.2, 22.5, 1.1, 0), F("ブラックコーヒー", 0, 0, 0, 0, kind="drink")],
]
LUNCH = [
    [F("鶏むね定食（ご飯並）", 650, 38, 14, 85, 4, 3.2), F("緑茶", 0, 0, 0, 0, kind="drink")],
    [F("ラーメン", 520, 20, 18, 70, 3, 6.0, upf=True), F("半チャーハン", 380, 9, 13, 55, 1, 1.8)],
    [F("コンビニおにぎり（鮭）", 180, 5, 1.5, 38, 1, 1.1, upf=True), F("サラダチキン", 110, 24, 1.5, 0.5, 0, 1.2), F("野菜サラダ", 40, 1.5, 0.3, 7, 2, 0.3)],
]
DINNER = [
    [F("ご飯", 234, 3.8, 0.5, 55.7, 2.3, 0, amount="150g"), F("鮭の塩焼き", 180, 22, 9, 0.1, 0, 1.4), F("ほうれん草のおひたし", 25, 2, 0.3, 3, 2.5, 0.5)],
    [F("豚の生姜焼き", 380, 22, 26, 10, 0.5, 2.2), F("ご飯", 312, 5, 0.6, 74, 3, 0, amount="200g"), F("キャベツ千切り", 15, 0.8, 0.1, 3.4, 1.2, 0)],
    [F("焼き鳥（5本）", 450, 35, 25, 15, 0, 3.0), F("ビール", 200, 1.5, 0, 15, kind="drink", amount="500ml", alc=20), F("枝豆", 125, 11, 6, 9, 5, 0.8)],
]
SNACK = [
    [F("プロテイン（ホエイ）", 120, 24, 1.5, 3, kind="drink", amount="1杯")],
    [F("ポテトチップス", 280, 2.5, 18, 27, 2, 0.5, upf=True)],
    [F("ハイボール", 140, 0, 0, 0, kind="drink", amount="500ml", alc=28)],
    [],
]

STRENGTH_PLAN = {0: ("胸・肩・腕", ["chest", "shoulders", "arms"], 16), 2: ("背中", ["back", "arms"], 14),
                 4: ("脚・お尻", ["legs", "glutes", "core"], 15)}


def seed(end: date, rng=random.Random(7)):
    with db.connect() as con:
        con.execute("DELETE FROM meals"); con.execute("DELETE FROM daily_health"); con.execute("DELETE FROM workouts")
        weight = 72.6
        for i in range(7):
            d = end - timedelta(days=6 - i)
            for slot, hh, menu in (("朝食", "07:10", BREAKFAST), ("昼食", "12:15", LUNCH), ("夕食", "19:20", DINNER), ("間食・飲み物", "21:05", SNACK)):
                items = rng.choice(menu)
                if items:
                    db.add_meal(con, eaten_at=f"{d}T{hh}", slot=slot, photo=None, items=items, confidence="demo")
            wd = d.weekday()
            workouts = []
            if wd in STRENGTH_PLAN:
                name, mg, sets = STRENGTH_PLAN[wd]
                workouts.append({"type": "strength", "name": name, "minutes": 60, "kcal": 250, "muscle_groups": mg, "sets": sets})
            if wd in (1, 5):
                workouts.append({"type": "running", "name": "ジョグ", "minutes": 40, "kcal": 380})
            if wd == 6:
                workouts.append({"type": "walking", "name": "散歩", "minutes": 50, "kcal": 180})
            active = 350 + sum(w["kcal"] for w in workouts) + rng.randint(-60, 80)
            weight -= rng.uniform(0.0, 0.2)
            health.ingest({"date": d.isoformat(), "source": "demo", "bmr_kcal": 1680, "active_kcal": active,
                           "total_burn_kcal": 1680 + active, "steps": rng.randint(5200, 11000),
                           "sleep_min": rng.randint(330, 450), "weight_kg": round(weight, 1), "workouts": workouts}, con)


if __name__ == "__main__":
    seed(date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today())
    print("seeded")
