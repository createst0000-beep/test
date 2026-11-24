"""記録ページ（claude.ai Artifact）のデータベースから書き出した JSON で週次レポートを作る。

  python scripts/report_from_artifact.py export.json --end 2026-11-24 --out reports/
  python scripts/report_from_artifact.py <ArtifactData の out_dir> --end 2026-11-24 --out reports/

export.json の形（ArtifactData の list 結果を集めたもの）:
  {"meals": [{...}], "health": [{...}], "workouts": [{...}], "settings": {"body_weight_kg": 72, "sex": "male", "bmr_kcal": 1650}}
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path


def _docs(v):
    """ArtifactData の list 結果（{id, data} の配列）でも、生のドキュメント配列でも受け付ける。"""
    out = []
    for d in v or []:
        out.append(d.get("data", d) if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) else d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("--end", help="最終日 YYYY-MM-DD（省略時は今日）")
    ap.add_argument("--out", default="reports")
    a = ap.parse_args()
    src = Path(a.export)
    if src.is_dir():
        # ArtifactData の out_dir 形式: <dir>/<collection>/<doc_id>.json
        load = lambda sub: [json.loads(f.read_text(encoding="utf-8")) for f in sorted((src / sub).glob("*.json"))] if (src / sub).is_dir() else []
        prof = src / "settings" / "profile.json"
        exp = {"meals": load("meals"), "health": load("health"), "workouts": load("workouts"),
               "settings": json.loads(prof.read_text(encoding="utf-8")) if prof.exists() else {}}
    else:
        exp = json.loads(src.read_text(encoding="utf-8"))
    settings = exp.get("settings") or {}
    if isinstance(settings, dict) and "data" in settings and isinstance(settings["data"], dict):
        settings = settings["data"]

    tmp = tempfile.mkdtemp()
    os.environ["MEAL_DATA_DIR"] = tmp
    os.environ["MEAL_REPORT_DIR"] = str(Path(a.out).resolve())
    if settings.get("body_weight_kg"):
        os.environ["BODY_WEIGHT_KG"] = str(settings["body_weight_kg"])
    if settings.get("sex"):
        os.environ["SEX"] = settings["sex"]
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app import db, energy, health, report  # noqa: E402  (環境変数を設定してから読み込む)

    bmr = settings.get("bmr_kcal")
    with db.connect() as con:
        for m in _docs(exp.get("meals")):
            if not m.get("date"):
                continue
            db.add_meal(con, eaten_at=f"{m['date']}T{m.get('time') or '12:00'}", slot=m.get("slot"),
                        photo=None, items=m.get("items") or [], confidence=m.get("confidence"), note=m.get("note"))
        for h in _docs(exp.get("health")):
            if not h.get("date"):
                continue
            h = dict(h)
            if not h.get("total_burn_kcal") and h.get("active_kcal") is not None:
                base = h.get("bmr_kcal") or bmr
                if base:
                    h["total_burn_kcal"] = float(base) + float(h["active_kcal"])
            h.pop("workouts", None)
            health.ingest({**h, "source": ",".join(h.get("sources") or []) or "screenshot"}, con)
        for i, w in enumerate(_docs(exp.get("workouts"))):
            if not w.get("date"):
                continue
            wtype = health.normalize_type(w.get("type"))
            kcal = w.get("kcal")
            if kcal is None and w.get("add_to_burn") and wtype == "strength":
                kcal = energy.strength_kcal(float(settings.get("body_weight_kg") or 70), w.get("minutes"), w.get("sets"))
            db.add_workout(con, date=w["date"], type=wtype, name=w.get("name"),
                           minutes=w.get("minutes"), kcal=kcal, muscle_groups=w.get("muscle_groups"),
                           sets=w.get("sets"), source=w.get("source") or "artifact", ext_id=f"artifact:{i}",
                           add_to_burn=bool(w.get("add_to_burn")))
    end = date.fromisoformat(a.end) if a.end else None
    path = report.build(end, Path(a.out))
    # claude.ai Artifact 用: 公開時に外枠が付くので、doctype/html/head/body タグを外したものも書き出す
    import re
    frag = re.sub(r"<!doctype html>|</?html[^>]*>|</?head>|</?body>|<meta charset=\"utf-8\">\s*|<meta name=\"viewport\"[^>]*>\s*",
                  "", path.read_text(encoding="utf-8"), flags=re.I)
    (Path(a.out) / "artifact.html").write_text(frag.strip() + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
