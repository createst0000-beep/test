"""1週間分のデータを集計し、エビデンスに基づく判定・アドバイスを作る。"""
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import config, db

STRENGTH_TYPES = {"strength", "weight_training", "筋トレ"}
MUSCLE_JA = {"chest": "胸", "back": "背中", "legs": "脚", "shoulders": "肩", "arms": "腕", "core": "体幹",
             "glutes": "お尻", "full_body": "全身"}
WORKOUT_JA = {"strength": "筋トレ", "walking": "ウォーキング", "running": "ランニング",
              "cycling": "サイクリング", "swimming": "水泳", "hiit": "HIIT", "yoga": "ヨガ", "other": "その他"}

# 判定レベル（レポートでアイコン＋ラベルを付ける）
GOOD, INFO, WARN, ALERT = "good", "info", "warn", "alert"


def _note(level, title, body, sources):
    return {"level": level, "title": title, "body": body, "sources": sources}


def week_range(end: date):
    start = end - timedelta(days=6)
    return [start + timedelta(days=i) for i in range(7)]


def analyze_week(end: date | None = None, con=None):
    from datetime import datetime
    end = end or datetime.now(config.TZ).date()
    days = week_range(end)
    s, e = days[0].isoformat(), days[-1].isoformat()

    if con is None:
        with db.connect() as c:
            return analyze_week(end, c)

    meals = db.meals_between(con, s, e)
    health = db.health_between(con, s, e)
    workouts = db.workouts_between(con, s, e)

    weights = [health[d]["weight_kg"] for d in sorted(health) if health[d].get("weight_kg")]
    bw = weights[-1] if weights else config.BODY_WEIGHT_KG

    # ---- 日別集計 ----
    daily = []
    meals_by_day = defaultdict(list)
    for m in meals:
        meals_by_day[m["date"]].append(m)
    wo_by_day = defaultdict(list)
    for w in workouts:
        wo_by_day[w["date"]].append(w)

    for d in days:
        k = d.isoformat()
        ms = meals_by_day.get(k, [])
        h = health.get(k, {})
        intake = sum(m["kcal"] for m in ms)
        burn = h.get("total_burn_kcal")
        if burn is None and h.get("bmr_kcal") is not None:
            burn = (h.get("bmr_kcal") or 0) + (h.get("active_kcal") or 0)
        # ウェアラブルを外していた運動（ジムなど）の上乗せ分
        extra = sum(w.get("kcal") or 0 for w in wo_by_day.get(k, []) if w.get("add_to_burn"))
        if burn is not None:
            burn += extra
        items = [it | {"slot": m["slot"], "time": m["eaten_at"][11:16]} for m in ms for it in m["items"]]
        daily.append({
            "date": k,
            "weekday": "月火水木金土日"[d.weekday()],
            "intake": round(intake),
            "burn": round(burn) if burn is not None else None,
            "net": round(intake - burn) if burn is not None and ms else None,
            "protein": round(sum(m["protein_g"] for m in ms), 1),
            "fat": round(sum(m["fat_g"] for m in ms), 1),
            "carb": round(sum(m["carb_g"] for m in ms), 1),
            "fiber": round(sum(m["fiber_g"] for m in ms), 1),
            "salt": round(sum(m["salt_g"] for m in ms), 1),
            "alcohol": round(sum(m["alcohol_g"] for m in ms), 1),
            "meal_count": len(ms),
            "protein_meals": sum(1 for m in ms if m["protein_g"] >= 0.4 * bw * 0.85),
            "items": items,
            "photos": [m["photo"] for m in ms if m["photo"]],
            "steps": h.get("steps"),
            "active": h.get("active_kcal"),
            "extra_burn": round(extra),
            "sleep_min": h.get("sleep_min"),
            "weight": h.get("weight_kg"),
            "workouts": wo_by_day.get(k, []),
        })

    # 今日がまだ終わっていない（21時前）なら、平均からは除く（途中の値で平均が下がるのを防ぐ）
    now = datetime.now(config.TZ)
    for x in daily:
        x["partial"] = x["date"] == now.date().isoformat() and now.hour < 21
    logged = [x for x in daily if x["meal_count"] > 0 and not x["partial"]]
    # 品目の内訳が無い日（塩分・食物繊維が0）は、塩分・食物繊維の平均から除く
    detailed = [x for x in logged if x["salt"] > 0 or x["fiber"] > 0]
    with_net = [x for x in daily if x["net"] is not None and not x["partial"]]

    def avg(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None

    summary = {
        "start": s, "end": e, "body_weight": bw,
        "days_logged": len(logged),
        "avg_intake": avg([x["intake"] for x in logged]),
        "avg_burn": avg([x["burn"] for x in daily]),
        "avg_net": avg([x["net"] for x in with_net]),
        "avg_protein": avg([x["protein"] for x in logged]),
        "avg_salt": avg([x["salt"] for x in detailed]),
        "avg_fiber": avg([x["fiber"] for x in detailed]),
        "alcohol_total": sum(x["alcohol"] for x in daily),
        "avg_steps": avg([x["steps"] for x in daily]),
        "avg_sleep_h": (avg([x["sleep_min"] for x in daily]) or 0) / 60 or None,
        "weight_first": weights[0] if weights else None,
        "weight_last": weights[-1] if weights else None,
    }
    lo, hi = config.TARGET_LOSS_KG_PER_MONTH
    summary["target_net"] = (-round(hi * config.KCAL_PER_KG_FAT / 30), -round(lo * config.KCAL_PER_KG_FAT / 30))
    if summary["avg_net"] is not None:
        summary["projected_kg_month"] = summary["avg_net"] * 30 / config.KCAL_PER_KG_FAT

    # ---- 食べたもの・飲んだもの ----
    food_counter, drink_counter = Counter(), Counter()
    kcal_by_name = defaultdict(float)
    upf_kcal = drink_kcal = total_kcal = 0.0
    for x in daily:
        for it in x["items"]:
            name = it.get("name", "不明")
            (drink_counter if it.get("kind") == "drink" else food_counter)[name] += 1
            kcal_by_name[name] += float(it.get("kcal") or 0)
            total_kcal += float(it.get("kcal") or 0)
            if it.get("ultra_processed"):
                upf_kcal += float(it.get("kcal") or 0)
            if it.get("kind") == "drink":
                drink_kcal += float(it.get("kcal") or 0)
    summary["upf_share"] = upf_kcal / total_kcal if total_kcal else 0
    summary["drink_share"] = drink_kcal / total_kcal if total_kcal else 0

    frequent = {
        "foods": [{"name": n, "count": c, "kcal": round(kcal_by_name[n])} for n, c in food_counter.most_common(8)],
        "drinks": [{"name": n, "count": c, "kcal": round(kcal_by_name[n])} for n, c in drink_counter.most_common(6)],
    }

    # ---- 運動集計 ----
    strength = [w for w in workouts if w["type"] in STRENGTH_TYPES]
    cardio = [w for w in workouts if w["type"] not in STRENGTH_TYPES]
    muscle_hits, muscle_sets = Counter(), Counter()
    for w in strength:
        groups = [g for g in (w.get("muscle_groups") or "").split(",") if g]
        for g in groups:
            muscle_hits[g] += 1
            if w.get("sets"):
                muscle_sets[g] += w["sets"] / len(groups)
    minutes_by_type = Counter()
    kcal_by_type = Counter()
    for w in workouts:
        minutes_by_type[w["type"]] += w.get("minutes") or 0
        kcal_by_type[w["type"]] += w.get("kcal") or 0
    exercise = {
        "strength_sessions": len({w["date"] for w in strength}),
        "cardio_minutes": sum(w.get("minutes") or 0 for w in cardio),
        "running_minutes": minutes_by_type.get("running", 0),
        "minutes_by_type": [{"type": t, "label": WORKOUT_JA.get(t, t), "minutes": round(m),
                             "kcal": round(kcal_by_type[t])} for t, m in minutes_by_type.most_common()],
        "muscle_hits": {MUSCLE_JA.get(g, g): c for g, c in muscle_hits.items()},
        "muscle_sets": {MUSCLE_JA.get(g, g): round(c) for g, c in muscle_sets.items()},
    }

    return {
        "summary": summary,
        "daily": daily,
        "frequent": frequent,
        "exercise": exercise,
        "food_notes": food_notes(summary, daily),
        "exercise_notes": exercise_notes(summary, daily, exercise),
    }


# ------------------------------------------------------------------
# 食事・飲み物の注意点
# ------------------------------------------------------------------
def food_notes(s, daily):
    notes = []
    bw = s["body_weight"]
    tlo, thi = s["target_net"]  # 例: (-770, -513)

    if s["days_logged"] < 5:
        notes.append(_note(WARN, "記録日数が不足",
                           f"今週の食事記録は{s['days_logged']}日分です。記録漏れがあると収支が実際より大きくマイナスに見えます。リマインド時に必ず1枚撮る習慣を。",
                           ["shcherbina2017"]))

    if s["avg_net"] is not None:
        net = s["avg_net"]
        proj = s.get("projected_kg_month", 0)
        if net > thi + 200:
            notes.append(_note(WARN, "カロリー収支のマイナスが足りない",
                               f"平均収支は{net:+.0f}kcal/日（推定{-proj:.1f}kg/月）。目標の月2〜3kg減には{tlo}〜{thi}kcal/日が必要です。まず飲み物・間食から100〜300kcal削るのが筋肉を守りやすい方法です。",
                               ["hall2008"]))
        elif net < -1000:
            notes.append(_note(ALERT, "マイナスが大きすぎる（筋肉が落ちるリスク）",
                               f"平均収支は{net:+.0f}kcal/日（推定{-proj:.1f}kg/月）。1日約500kcalを超える不足は筋トレによる除脂肪量の維持・増加を妨げやすく、週1%を超える減量は筋力低下を招きやすいです。炭水化物を中心に200〜300kcal戻してください。",
                               ["murphy2022", "helms2014", "garthe2011"]))
        else:
            if net < tlo:
                title, lvl = "カロリー収支のマイナスがやや大きい", WARN
                body = f"目標は{tlo}〜{thi}kcal/日で、約{tlo - net:.0f}kcal超えています。筋トレ中は不足を広げすぎず、たんぱく質を中心に食べる量を少し戻してください。"
            elif net > thi:
                title, lvl = "カロリー収支は目標にほぼ届いている", INFO
                body = f"目標は{tlo}〜{thi}kcal/日で、あと約{net - thi:.0f}kcal足りません。"
            else:
                title, lvl = "カロリー収支は目標範囲", GOOD
                body = f"目標の{tlo}〜{thi}kcal/日に収まっています。"
            notes.append(_note(lvl, title,
                               f"平均収支は{net:+.0f}kcal/日（推定{-proj:.1f}kg/月）。{body}約500kcalを超える不足は筋量維持に不利になり得るため、筋トレ中は−500前後に寄せるのが安全です。",
                               ["hall2008", "murphy2022"]))
        notes.append(_note(INFO, "消費カロリーは誤差を見込む",
                           "スマホやリングの消費カロリーは20%以上ずれることがあります。収支だけでなく、体重の週平均の推移（月2〜3kg減＝週0.5〜0.75kg）で答え合わせをしてください。",
                           ["shcherbina2017"]))

    if s["weight_first"] and s["weight_last"]:
        pct = (s["weight_last"] - s["weight_first"]) / s["weight_first"] * 100
        if pct < -1.0:
            notes.append(_note(ALERT, "体重の落ち方が速い",
                               f"今週は{pct:.1f}%変化。筋量を守るなら週0.5〜1%が上限の目安です（水分変動も含むため2週連続なら摂取を増やす）。",
                               ["helms2014", "garthe2011"]))

    if s["avg_protein"] is not None:
        gkg = s["avg_protein"] / bw
        need_lo, need_hi = round(1.6 * bw), round(2.2 * bw)
        if gkg < 1.6:
            notes.append(_note(ALERT, "たんぱく質不足（筋肉維持の最重要項目）",
                               f"平均{s['avg_protein']:.0f}g/日＝{gkg:.2f}g/kg。減量中の筋トレなら最低1.6g/kg（{need_lo}g）、できれば2.0〜2.4g/kgを。鶏むね・卵・魚・ギリシャヨーグルト・プロテインで1食20〜40gを足してください。",
                               ["morton2018", "longland2016", "jager2017"]))
        elif gkg < 2.0:
            notes.append(_note(INFO, "たんぱく質は最低ラインはクリア",
                               f"平均{gkg:.2f}g/kg。カロリー制限中は2.0g/kg以上（{round(2.0*bw)}g〜）で除脂肪量がより守られやすいです。",
                               ["longland2016", "helms2014"]))
        else:
            notes.append(_note(GOOD, "たんぱく質量は十分",
                               f"平均{gkg:.2f}g/kg（目安1.6〜2.2g/kg＝{need_lo}〜{need_hi}g、減量中は2.0〜2.4g/kg）。",
                               ["morton2018", "longland2016"]))
        avg_pm = sum(x["protein_meals"] for x in daily if x["meal_count"]) / max(1, s["days_logged"])
        if avg_pm < 3:
            notes.append(_note(INFO, "たんぱく質の配分",
                               f"1食{round(0.4*bw)}g（0.4g/kg）以上を満たす食事が1日平均{avg_pm:.1f}回。3〜4回に分けると筋合成に有利です。朝食に卵2個＋ヨーグルト等を。",
                               ["schoenfeld2018", "jager2017"]))

    limit = 7.5 if config.SEX == "male" else 6.5
    if s["avg_salt"] and s["avg_salt"] > limit:
        notes.append(_note(WARN, "塩分が多い",
                           f"平均{s['avg_salt']:.1f}g/日（目標{limit}g未満）。塩分は一時的な水分増で体重を押し上げ、減量の判断も狂わせます。麺類のスープ・漬物・加工肉を控えめに。",
                           ["mhlw_dri2020"]))
    fiber_t = 21 if config.SEX == "male" else 18
    if s["avg_fiber"] is not None and s["avg_fiber"] < fiber_t:
        notes.append(_note(INFO, "食物繊維が不足",
                           f"平均{s['avg_fiber']:.0f}g/日（目標{fiber_t}g以上）。野菜・海藻・きのこ・オートミール・豆類で満腹感も上がります。",
                           ["mhlw_dri2020"]))

    if s["upf_share"] > 0.3:
        notes.append(_note(WARN, "加工食品の比率が高い",
                           f"摂取カロリーの{s['upf_share']*100:.0f}%が菓子・菓子パン・カップ麺などの超加工食品。超加工食品中心だと自然に1日約500kcal食べ過ぎることが示されています。",
                           ["hall2019"]))
    if s["drink_share"] > 0.1:
        notes.append(_note(WARN, "飲み物のカロリー",
                           f"摂取カロリーの{s['drink_share']*100:.0f}%が飲み物。液体のカロリーは満腹感につながりにくいため、最初に削る候補です。",
                           ["hall2019"]))

    if s["alcohol_total"] > 0:
        heavy_days = [x for x in daily if x["alcohol"] > 20]
        post_wo = [x for x in daily if x["alcohol"] > 20 and any(w["type"] in STRENGTH_TYPES for w in x["workouts"])]
        lvl = WARN if heavy_days else INFO
        body = f"今週の純アルコール合計{s['alcohol_total']:.0f}g。1日20gを超えた日が{len(heavy_days)}日。"
        if post_wo:
            body += f"うち{len(post_wo)}日は筋トレ当日。運動後の飲酒は筋たんぱく合成を24〜37%下げるため、トレ日は飲まないのが筋肉には得策です。"
        notes.append(_note(lvl, "アルコール", body, ["mhlw_alcohol", "parr2014"]))
    return notes


# ------------------------------------------------------------------
# 運動の特徴・注意点
# ------------------------------------------------------------------
def exercise_notes(s, daily, ex):
    notes = []
    n = ex["strength_sessions"]
    if n < 2:
        notes.append(_note(ALERT, "筋トレ頻度が不足",
                           f"今週の筋トレは{n}日。減量中に筋肉を残す最大のシグナルは筋トレです。各部位を週2回以上（全身法なら週2〜3回）を確保してください。",
                           ["schoenfeld2016freq", "helms2014"]))
    else:
        notes.append(_note(GOOD, "筋トレ頻度は良好", f"今週の筋トレは{n}日。減量中も重量（強度）を落とさないことが筋量維持の鍵です。",
                           ["schoenfeld2016freq", "helms2014"]))

    once = [g for g, c in ex["muscle_hits"].items() if c < 2]
    if ex["muscle_hits"] and once:
        notes.append(_note(INFO, "週1回しか刺激していない部位",
                           f"{'・'.join(once)}は今週1回のみ。週2回に分けると同じ総セット数でも筋肥大に有利です。",
                           ["schoenfeld2016freq"]))
    low_vol = [g for g, v in ex["muscle_sets"].items() if v < 10]
    if low_vol:
        notes.append(_note(INFO, "部位別ボリューム",
                           f"{'・'.join(low_vol)}は週10セット未満。減量中は維持目的なら現状維持でも可ですが、筋量を増やしたい部位は週10セット以上を目安に。",
                           ["schoenfeld2017vol"]))

    if ex["running_minutes"] > 120 and n >= 1:
        notes.append(_note(WARN, "有酸素の干渉効果",
                           f"今週のランニングは{ex['running_minutes']:.0f}分。有酸素は量が多いほど筋トレ効果を干渉し、特にランニングで顕著です。消費を増やすならウォーキング・自転車に置き換え、筋トレとは時間を空けて。",
                           ["wilson2012"]))

    if s["avg_steps"] is not None:
        if s["avg_steps"] < 8000:
            notes.append(_note(INFO, "日常の歩数",
                               f"平均{s['avg_steps']:.0f}歩/日。歩数（日常活動）を増やすのは筋トレへの干渉が小さい消費の上乗せ方法です。8,000〜10,000歩を目安に。",
                               ["paluch2022", "wilson2012"]))
        else:
            notes.append(_note(GOOD, "日常の歩数は十分", f"平均{s['avg_steps']:.0f}歩/日。", ["paluch2022"]))

    if s["avg_sleep_h"]:
        if s["avg_sleep_h"] < 7:
            notes.append(_note(ALERT, "睡眠不足は筋肉を減らす",
                               f"平均睡眠{s['avg_sleep_h']:.1f}時間（SOXAI等）。同じ食事制限でも睡眠5.5時間では除脂肪量の減少が60%多くなりました。7時間以上を最優先に。",
                               ["nedeltcheva2010"]))
        else:
            notes.append(_note(GOOD, "睡眠時間", f"平均{s['avg_sleep_h']:.1f}時間。", ["nedeltcheva2010"]))
    return notes
