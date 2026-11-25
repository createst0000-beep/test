"""週次レポート（HTML）を生成する。グラフは外部ライブラリなしのインライン SVG。

使い方:  python -m app.report [--end 2026-11-23] [--out reports/]
"""
import argparse
import html
import json
from datetime import date, datetime

from . import analysis, config
from .evidence import cite_list

E = html.escape
LEVEL = {
    "good": ("✓", "良好"),
    "info": ("i", "ヒント"),
    "warn": ("!", "注意"),
    "alert": ("‼", "要改善"),
}


def _fmt(v, nd=0, unit=""):
    if v is None:
        return "—"
    return f"{v:,.{nd}f}{unit}"


def _ticks(vmax):
    """0 から vmax 以上までのきりのよい目盛り。"""
    step = _nice_max(vmax / 5)
    n = int(-(-vmax // step))
    return step * n, [step * i for i in range(n + 1)]


def _nice_max(v):
    if v <= 0:
        return 1
    import math
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


# ------------------------------------------------------------ SVG helpers
def _col_path(x, y0, w, h, r=4):
    """上端だけ角丸の縦棒（下端はベースラインに接して角なし）。h<0 で下向き。"""
    if abs(h) < 0.5:
        return ""
    r = min(r, abs(h), w / 2)
    if h > 0:
        top = y0 - h
        return (f"M{x},{y0}V{top + r}Q{x},{top} {x + r},{top}H{x + w - r}"
                f"Q{x + w},{top} {x + w},{top + r}V{y0}Z")
    bot = y0 - h
    return (f"M{x},{y0}V{bot - r}Q{x},{bot} {x + r},{bot}H{x + w - r}"
            f"Q{x + w},{bot} {x + w},{bot - r}V{y0}Z")


def chart_intake_burn(daily):
    """摂取 vs 消費（グループ縦棒）。"""
    W, H, L, R, T, B = 640, 260, 48, 12, 16, 34
    vmax, ticks = _ticks(max([d["intake"] for d in daily] + [d["burn"] or 0 for d in daily] + [1000]))
    pw, ph = W - L - R, H - T - B
    band = pw / len(daily)
    bw = min(20, band / 3)
    y = lambda v: T + ph - v / vmax * ph
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="1日ごとの摂取カロリーと消費カロリー">']
    for v in ticks:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="tick" text-anchor="end">{v:,.0f}</text>')
    for i, d in enumerate(daily):
        cx = L + band * i + band / 2
        tip = f"{d['date'][5:]}（{d['weekday']}）|摂取 {_fmt(d['intake'])} kcal|消費 {_fmt(d['burn'])} kcal|収支 {_fmt(d['net'])} kcal"
        out.append(f'<g class="hit" data-tip="{E(tip)}"><rect x="{cx - band / 2}" y="{T}" width="{band}" height="{ph}" fill="transparent"/>')
        out.append(f'<path d="{_col_path(cx - bw - 1, y(0), bw, d["intake"] / vmax * ph)}" fill="var(--s1)"/>')
        if d["burn"]:
            out.append(f'<path d="{_col_path(cx + 1, y(0), bw, d["burn"] / vmax * ph)}" fill="var(--s2)"/>')
        out.append("</g>")
        out.append(f'<text x="{cx}" y="{H - 8}" class="tick" text-anchor="middle">{int(d["date"][8:])}{d["weekday"]}</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(0)}" y2="{y(0)}" class="axis"/></svg>')
    legend = ('<div class="legend"><span><i style="background:var(--s1)"></i>摂取カロリー</span>'
              '<span><i style="background:var(--s2)"></i>消費カロリー（Fit／リング）</span></div>')
    return legend + "".join(out)


def chart_net(daily, target):
    """1日ごとの総カロリー収支（摂取−消費）。目標帯つき。"""
    W, H, L, R, T, B = 640, 240, 48, 12, 16, 34
    vals = [d["net"] for d in daily if d["net"] is not None]
    lim = _nice_max(max([abs(v) for v in vals] + [abs(target[0]) + 100]))
    pw, ph = W - L - R, H - T - B
    band = pw / len(daily)
    bw = min(24, band * 0.5)
    y = lambda v: T + ph / 2 - v / lim * (ph / 2)
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="1日ごとの総カロリー収支">']
    out.append(f'<rect x="{L}" y="{y(target[1]):.1f}" width="{pw}" height="{y(target[0]) - y(target[1]):.1f}" class="band"/>')
    for v in (-lim, -lim / 2, lim / 2, lim):
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>')
    for v in (-lim, -lim / 2, 0, lim / 2, lim):
        out.append(f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="tick" text-anchor="end">{v:+,.0f}</text>')
    for i, d in enumerate(daily):
        cx = L + band * i + band / 2
        n = d["net"]
        tip = f"{d['date'][5:]}（{d['weekday']}）|収支 {_fmt(n)} kcal" if n is not None else f"{d['date'][5:]}|データなし"
        out.append(f'<g class="hit" data-tip="{E(tip)}"><rect x="{cx - band / 2}" y="{T}" width="{band}" height="{ph}" fill="transparent"/>')
        if n is not None:
            color = "var(--neg)" if n < 0 else "var(--pos)"
            out.append(f'<path d="{_col_path(cx - bw / 2, y(0), bw, n / lim * ph / 2)}" fill="{color}"/>')
            ly = y(n) + (14 if n < 0 else -6)
            out.append(f'<text x="{cx}" y="{ly:.1f}" class="val" text-anchor="middle">{n:+,}</text>')
        out.append("</g>")
        out.append(f'<text x="{cx}" y="{H - 8}" class="tick" text-anchor="middle">{int(d["date"][8:])}{d["weekday"]}</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(0)}" y2="{y(0)}" class="axis"/></svg>')
    legend = (f'<div class="legend"><span><i style="background:var(--neg)"></i>マイナス（減量方向）</span>'
              '<span><i style="background:var(--pos)"></i>プラス（超過）</span>'
              f'<span><i class="bandkey"></i>月2〜3kg減の目標帯（{target[0]}〜{target[1]} kcal）</span></div>')
    return legend + "".join(out)


def chart_protein(daily, bw):
    """たんぱく質 g/日（目標ライン 1.6・2.0 g/kg）。"""
    W, H, L, R, T, B = 640, 200, 48, 12, 16, 34
    lo, mid = 1.6 * bw, 2.0 * bw
    vmax, ticks = _ticks(max([d["protein"] for d in daily] + [mid * 1.15]))
    pw, ph = W - L - R, H - T - B
    band = pw / len(daily)
    bw_ = min(24, band * 0.5)
    y = lambda v: T + ph - v / vmax * ph
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="たんぱく質摂取量">']
    for v in ticks:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="tick" text-anchor="end">{v:,.0f}</text>')
    for i, d in enumerate(daily):
        cx = L + band * i + band / 2
        tip = f"{d['date'][5:]}（{d['weekday']}）|たんぱく質 {d['protein']:.0f} g（{d['protein'] / bw:.2f} g/kg）|脂質 {d['fat']:.0f} g・炭水化物 {d['carb']:.0f} g"
        out.append(f'<g class="hit" data-tip="{E(tip)}"><rect x="{cx - band / 2}" y="{T}" width="{band}" height="{ph}" fill="transparent"/>')
        out.append(f'<path d="{_col_path(cx - bw_ / 2, y(0), bw_, d["protein"] / vmax * ph)}" fill="var(--s3)"/></g>')
        out.append(f'<text x="{cx}" y="{H - 8}" class="tick" text-anchor="middle">{int(d["date"][8:])}{d["weekday"]}</text>')
    for v, lab in ((lo, "1.6 g/kg（最低）"), (mid, "2.0 g/kg（減量中の目安）")):
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="ref"/>'
                   f'<text x="{W - R - 4}" y="{y(v) - 4:.1f}" class="tick" text-anchor="end">{lab} {v:.0f} g</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(0)}" y2="{y(0)}" class="axis"/></svg>')
    return "".join(out)


def hbar_list(rows, value_key, unit, color="var(--s1)", label_key="name", tip_fn=None):
    if not rows:
        return '<p class="muted">データがありません</p>'
    vmax = max(r[value_key] for r in rows) or 1
    out = ['<div class="hbars">']
    for r in rows:
        pct = r[value_key] / vmax * 100
        tip = tip_fn(r) if tip_fn else f"{r[label_key]}|{r[value_key]}{unit}"
        out.append(f'<div class="hrow hit" data-tip="{E(tip)}"><span class="hl">{E(str(r[label_key]))}</span>'
                   f'<span class="ht"><span class="hb" style="width:{pct:.1f}%;background:{color}"></span></span>'
                   f'<span class="hv">{r[value_key]:,}{unit}</span></div>')
    out.append("</div>")
    return "".join(out)


MUSCLE_ORDER = ["chest", "back", "legs", "shoulders", "arms", "glutes", "core"]


def exercise_html(daily, ex):
    """運動内容: 週のまとめ → 部位ごとの達成状況 → 日ごとのカード。"""
    wos = [(d, w) for d in daily for w in d["workouts"]]
    if not wos:
        return '<p class="muted">今週の運動記録はまだありません。</p>'
    strength = [w for _, w in wos if w["type"] in analysis.STRENGTH_TYPES]
    cardio = [w for _, w in wos if w["type"] not in analysis.STRENGTH_TYPES]
    total_sets = sum(w.get("sets") or 0 for w in strength)
    cardio_min = sum(w.get("minutes") or 0 for w in cardio)
    gym_kcal = sum(w.get("kcal") or 0 for _, w in wos if w.get("add_to_burn"))
    summary = [
        ("筋トレ", f'{ex["strength_sessions"]} 日', "目安 週2日以上"),
        ("筋トレのセット数", f"{total_sets} セット", "記録のある種目の合計"),
        ("有酸素", f"{cardio_min:.0f} 分" if cardio_min else "—", "傾斜ウォークなど"),
        ("ジムの消費（上乗せ分）", f"{gym_kcal:,.0f} kcal", "リング・Fit 未装着の分"),
    ]
    out = ['<div class="tiles">' + "".join(
        f'<div class="tile"><div class="tl">{a}</div><div class="tv">{b}</div><div class="ts">{c}</div></div>'
        for a, b, c in summary) + "</div>"]

    # 部位ごとの達成状況
    hits, sets = {}, {}
    for w in strength:
        for g in [g for g in (w.get("muscle_groups") or "").split(",") if g]:
            hits[g] = hits.get(g, 0) + 1
            sets[g] = sets.get(g, 0) + (w.get("sets") or 0)
    rows = []
    for g in MUSCLE_ORDER:
        h, st = hits.get(g, 0), sets.get(g, 0)
        if h >= 2 and st >= 10:
            cls, mark, lab = "good", "✓", "達成"
        elif h >= 2:
            cls, mark, lab = "ok", "○", "頻度OK"
        elif h == 1:
            cls, mark, lab = "warn", "△", "あと1回"
        else:
            cls, mark, lab = "none", "—", "未実施"
        dots = "".join(f'<i class="dot{" on" if i < h else ""}"></i>' for i in range(max(2, h)))
        rows.append(f'<div class="mrow {cls}"><span class="mname">{analysis.MUSCLE_JA[g]}</span>'
                    f'<span class="dots" aria-label="週{h}回">{dots}</span>'
                    f'<span class="mstat">{h}回・{st or "—"}セット</span>'
                    f'<span class="mbadge"><b>{mark}</b>{lab}</span></div>')
    out.append('<h3>部位ごとの達成状況（目安: 週2回・週10セット）</h3><div class="mgrid">' + "".join(rows) + "</div>")

    # 日ごとのカード
    out.append("<h3>日ごとの記録</h3>")
    for d in daily:
        if not d["workouts"]:
            continue
        kcal = sum((w.get("kcal") or 0) for w in d["workouts"] if w.get("add_to_burn"))
        items = []
        for w in d["workouts"]:
            name = w.get("name") or analysis.WORKOUT_JA.get(w["type"], w["type"])
            # 「種目名 重量×回数×セット」形式なら、種目名と内容に分けて表示する
            name, detail = (name.split(" ", 1) + [""])[:2] if " " in name.strip() else (name, "")
            kind = analysis.WORKOUT_JA.get(w["type"], w["type"])
            chips = "".join(f'<span class="chip">{E(analysis.MUSCLE_JA.get(g, g))}</span>'
                            for g in (w.get("muscle_groups") or "").split(",") if g)
            meta = " ・ ".join(x for x in [kind, f'{w["minutes"]:.0f}分' if w.get("minutes") else "",
                                            f'{w["sets"]}セット' if w.get("sets") else ""] if x)
            k = f'+{w["kcal"]:.0f} kcal' if w.get("kcal") and w.get("add_to_burn") else (f'{w["kcal"]:.0f} kcal' if w.get("kcal") else "")
            items.append(f'<div class="exrow"><div class="exmain"><div class="exname">{E(name)}</div>'
                         + (f'<div class="exdetail">{E(detail)}</div>' if detail else "")
                         + f'<div class="exmeta">{E(meta)} {chips}</div></div><div class="exkcal">{E(k)}</div></div>')
        out.append(f'<div class="daycard"><div class="dayhead"><b>{d["date"][5:]}（{d["weekday"]}）</b>'
                   f'<span class="muted">{len(d["workouts"])}種目{f"・上乗せ {kcal:,.0f} kcal" if kcal else ""}</span></div>'
                   + "".join(items) + "</div>")
    out.append('<p class="muted" style="font-size:.78rem">「+」付きの kcal は、リング・Fit を外していた運動として1日の消費に足した分です（安静時の分は除いています）。</p>')
    return "".join(out)


# ------------------------------------------------------------ page
def render(data):
    s, daily, fr, ex = data["summary"], data["daily"], data["frequent"], data["exercise"]
    bw = s["body_weight"]
    tiles = [
        ("平均収支", _fmt(s["avg_net"], 0, " kcal"), f"目標 {s['target_net'][0]}〜{s['target_net'][1]}"),
        ("推定ペース", (f"{s['projected_kg_month']:+.1f} kg/月".replace("-", "−") if s.get("projected_kg_month") is not None else "—"), "目標 −2〜−3 kg/月"),
        ("平均摂取", _fmt(s["avg_intake"], 0, " kcal"), f"記録 {s['days_logged']}/7日"),
        ("平均消費", _fmt(s["avg_burn"], 0, " kcal"), "Fit・SOXAI"),
        ("たんぱく質", (f"{s['avg_protein'] / bw:.2f} g/kg" if s["avg_protein"] else "—"), f"目安 2.0 g/kg＝{2.0 * bw:.0f} g"),
        ("筋トレ", f"{ex['strength_sessions']} 日", "目安 週2日以上"),
    ]
    weight_line = ""
    if s["weight_first"] and s["weight_last"]:
        weight_line = f"体重 {s['weight_first']:.1f} → {s['weight_last']:.1f} kg（{s['weight_last'] - s['weight_first']:+.1f} kg）"

    def notes_html(notes):
        out = []
        for n in notes:
            icon, lab = LEVEL[n["level"]]
            srcs = "".join(f'<li>{(f"<a href=\"{E(c["url"])}\" target=\"_blank\" rel=\"noopener\">{E(c["cite"])}</a>" if c["url"] else E(c["cite"]))}<br><span class="muted">{E(c["point"])}</span></li>'
                           for c in cite_list(n["sources"]))
            out.append(f'<article class="note {n["level"]}"><header><span class="badge"><b>{icon}</b>{lab}</span>'
                       f'<h4>{E(n["title"])}</h4></header><p>{E(n["body"])}</p>'
                       f'<details><summary>根拠となる文献</summary><ul>{srcs}</ul></details></article>')
        return "".join(out)

    # 食べたもの飲んだもの（日別）
    day_items = []
    for d in daily:
        if not d["items"]:
            day_items.append(f'<details class="day"><summary><b>{d["date"][5:]}（{d["weekday"]}）</b><span class="muted">記録なし</span></summary></details>')
            continue
        rows = "".join(
            f'<tr><td>{E(it.get("time", ""))}</td><td>{E(it.get("slot") or "")}</td>'
            f'<td>{"🥤 " if it.get("kind") == "drink" else ""}{E(it.get("name", ""))}<span class="muted"> {E(it.get("amount") or "")}</span></td>'
            f'<td class="num">{_fmt(it.get("kcal"))}</td><td class="num">{_fmt(it.get("protein_g"), 0)}</td></tr>'
            for it in d["items"])
        day_items.append(f'<details class="day"><summary><b>{d["date"][5:]}（{d["weekday"]}）</b>'
                         f'<span>{_fmt(d["intake"])} kcal・P {d["protein"]:.0f} g</span></summary>'
                         f'<table><thead><tr><th>時刻</th><th>区分</th><th>品目</th><th class="num">kcal</th><th class="num">P(g)</th></tr></thead><tbody>{rows}</tbody></table></details>')

    table_rows = "".join(
        f'<tr><td>{d["date"][5:]}（{d["weekday"]}）{"<br><span class=muted>集計中</span>" if d.get("partial") else ""}</td><td class="num">{_fmt(d["intake"])}</td><td class="num">{_fmt(d["burn"])}</td>'
        f'<td class="num">{_fmt(d["net"])}</td><td class="num">{d["protein"]:.0f}</td><td class="num">{_fmt(d["steps"])}</td>'
        f'<td class="num">{_fmt((d["sleep_min"] or 0) / 60 if d["sleep_min"] else None, 1)}</td><td class="num">{_fmt(d["weight"], 1)}</td></tr>'
        for d in daily)

    generated = datetime.now(config.TZ).strftime("%Y-%m-%d %H:%M")
    return TEMPLATE.format(
        start=s["start"], end=s["end"], generated=generated, weight_line=E(weight_line),
        tiles="".join(f'<div class="tile"><div class="tl">{a}</div><div class="tv">{b}</div><div class="ts">{c}</div></div>' for a, b, c in tiles),
        chart_net=chart_net(daily, s["target_net"]),
        chart_ib=chart_intake_burn(daily),
        chart_p=chart_protein(daily, bw),
        table_rows=table_rows,
        day_items="".join(day_items),
        foods=hbar_list(fr["foods"], "count", " 回", "var(--s1)", tip_fn=lambda r: f"{r['name']}|{r['count']} 回|計 {r['kcal']:,} kcal"),
        drinks=hbar_list(fr["drinks"], "count", " 回", "var(--s2)", tip_fn=lambda r: f"{r['name']}|{r['count']} 回|計 {r['kcal']:,} kcal"),
        food_notes=notes_html(data["food_notes"]),
        exercise=exercise_html(daily, ex),
        ex_notes=notes_html(data["exercise_notes"]),
    )


TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>週間カロリーレポート</title>
<style>
:root{{color-scheme:light;--bg:#f6f5f2;--surface:#fcfcfb;--line:#e4e2dc;--grid:#ecebe6;--ink:#0b0b0b;--ink2:#52514e;--muted:#7a7974;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--neg:#2a78d6;--pos:#e34948;--band:rgba(42,120,214,.08);
--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--critical:#d03b3b;--info:#52514e}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#121211;--surface:#1a1a19;--line:#33332f;--grid:#2a2a27;--ink:#f0efec;--ink2:#c3c2b7;--muted:#96958d;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--neg:#3987e5;--pos:#e66767;--band:rgba(57,135,229,.12);--info:#c3c2b7}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#121211;--surface:#1a1a19;--line:#33332f;--grid:#2a2a27;--ink:#f0efec;--ink2:#c3c2b7;--muted:#96958d;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--neg:#3987e5;--pos:#e66767;--band:rgba(57,135,229,.12);--info:#c3c2b7}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}}
main{{max-width:960px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:1.5rem;margin:0 0 4px}} h2{{font-size:1.15rem;margin:0 0 12px}} h3{{font-size:.95rem;margin:16px 0 8px;color:var(--ink2)}}
.muted{{color:var(--muted)}} .sub{{color:var(--ink2);margin:0 0 20px}}
section{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px 16px;margin:0 0 16px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px}}
.tile{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
.tl{{font-size:.8rem;color:var(--ink2)}} .tv{{font-size:1.35rem;font-weight:600;font-variant-numeric:tabular-nums}} .ts{{font-size:.75rem;color:var(--muted)}}
.chart{{width:100%;height:auto;display:block;overflow:visible}}
.grid{{stroke:var(--grid);stroke-width:1}} .axis{{stroke:var(--ink2);stroke-width:1}} .ref{{stroke:var(--ink2);stroke-width:1;opacity:.6}}
.band{{fill:var(--band)}} .tick{{fill:var(--muted);font-size:11px}} .val{{fill:var(--ink2);font-size:11px;font-variant-numeric:tabular-nums}}
@media (max-width:640px){{.tick,.val{{font-size:18px}} .chart{{margin-left:6px;width:calc(100% - 6px)}}}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.82rem;color:var(--ink2);margin-bottom:6px}}
.legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}}
.legend .bandkey{{background:var(--band);outline:1px solid var(--line)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} @media (max-width:640px){{.two{{grid-template-columns:1fr}}}}
.hbars{{display:flex;flex-direction:column;gap:6px}}
.hrow{{display:grid;grid-template-columns:minmax(80px,38%) 1fr auto;gap:8px;align-items:center;font-size:.88rem}}
.hl{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}} .ht{{height:12px}} .hb{{display:block;height:12px;border-radius:0 4px 4px 0;min-width:2px}}
.hv{{color:var(--ink2);font-variant-numeric:tabular-nums;font-size:.82rem}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}} th,td{{padding:6px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--ink2);font-weight:500}} .num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.scroll{{overflow-x:auto}}
details.day{{border-bottom:1px solid var(--line);padding:8px 0}} details.day summary{{cursor:pointer;display:flex;justify-content:space-between;gap:8px}}
.note{{border:1px solid var(--line);border-left:4px solid var(--info);border-radius:8px;padding:10px 12px;margin:0 0 10px}}
.note.good{{border-left-color:var(--good)}} .note.warn{{border-left-color:var(--warn)}} .note.alert{{border-left-color:var(--critical)}}
.note header{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}} .note h4{{margin:0;font-size:.95rem}} .note p{{margin:6px 0}}
.badge{{font-size:.72rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--ink2)}} .badge b{{margin-right:4px}}
.note.good .badge b{{color:var(--good)}} .note.alert .badge b{{color:var(--critical)}} .note.warn .badge b{{color:var(--serious)}}
.note details{{font-size:.8rem}} .note summary{{cursor:pointer;color:var(--ink2)}} .note ul{{padding-left:18px;margin:6px 0}} .note a{{color:var(--ink2)}}
.mgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:6px}}
.mrow{{display:grid;grid-template-columns:3.5em auto 1fr auto;gap:10px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:.88rem}}
.mname{{font-weight:600}} .mstat{{color:var(--ink2);font-variant-numeric:tabular-nums;font-size:.82rem}}
.dots{{display:flex;gap:4px}} .dot{{width:10px;height:10px;border-radius:50%;border:1.5px solid var(--line);display:inline-block}} .dot.on{{background:var(--s3);border-color:var(--s3)}}
.mbadge{{font-size:.75rem;border:1px solid var(--line);border-radius:999px;padding:1px 8px;color:var(--ink2);white-space:nowrap}} .mbadge b{{margin-right:3px}}
.mrow.good .mbadge b{{color:var(--good)}} .mrow.ok .mbadge b{{color:var(--good)}} .mrow.warn .mbadge b{{color:var(--serious)}} .mrow.none{{opacity:.6}}
.daycard{{border:1px solid var(--line);border-radius:10px;margin:0 0 10px;overflow:hidden}}
.dayhead{{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:8px 12px;background:var(--bg);border-bottom:1px solid var(--line);font-size:.9rem}}
.exrow{{display:flex;justify-content:space-between;gap:10px;padding:8px 12px;border-top:1px solid var(--line)}} .dayhead+.exrow{{border-top:0}}
.exmain{{min-width:0}} .exname{{font-weight:600;font-size:.9rem;overflow-wrap:anywhere}} .exmeta{{color:var(--ink2);font-size:.8rem;margin-top:2px}}
.exdetail{{font-size:.86rem;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}}
.exkcal{{white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--ink2);font-size:.85rem}}
.chip{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 7px;margin:2px 2px 0 0;font-size:.72rem;color:var(--ink2)}}
#tip{{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:.8rem;box-shadow:0 4px 14px rgba(0,0,0,.12);display:none;z-index:9;white-space:nowrap}}
#tip b{{display:block}} .hit:hover path,.hit:hover .hb{{opacity:.8}}
</style></head><body><main>
<h1>週間カロリーレポート</h1>
<p style="margin:0 0 12px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface)">このページは記録の更新に合わせて作り直しています（毎日22時にも自動更新）。記録した直後の数字は、記録ページの「週間レポート」タブでリアルタイムに見られます：<a href="https://claude.ai/artifact/3HUAV7ay7hQkh7jh9RpXBk#report" target="_blank" rel="noopener">最新のレポートを開く</a></p>
<p class="sub">{start} 〜 {end}　{weight_line}　<span class="muted">生成 {generated}</span></p>
<div class="tiles">{tiles}</div>

<section><h2>1日ごとの総カロリー（摂取 − 消費）</h2>{chart_net}</section>
<section><h2>摂取カロリーと消費カロリー</h2>{chart_ib}
<h3>表で見る</h3><div class="scroll"><table><thead><tr><th>日付</th><th class="num">摂取</th><th class="num">消費</th><th class="num">収支</th><th class="num">P(g)</th><th class="num">歩数</th><th class="num">睡眠(h)</th><th class="num">体重</th></tr></thead><tbody>{table_rows}</tbody></table></div></section>
<section><h2>たんぱく質（筋肉維持チェック）</h2>{chart_p}</section>

<section><h2>食べたもの・飲んだもの</h2>{day_items}</section>
<section><h2>よく食べているもの・飲んでいるもの</h2><div class="two"><div><h3>食べ物（回数）</h3>{foods}</div><div><h3>飲み物（回数）</h3>{drinks}</div></div></section>
<section><h2>食事・飲み物についての注意点</h2>{food_notes}</section>

<section><h2>運動内容</h2>{exercise}</section>
<section><h2>運動についての特徴・注意点</h2>{ex_notes}</section>
<p class="muted" style="font-size:.78rem">写真からのカロリー推定と、ウェアラブルの消費カロリーにはどちらも誤差があります。体重の週平均の推移と合わせて判断してください。持病や服薬がある場合は医師・管理栄養士に相談してください。</p>
</main><div id="tip"></div>
<script>
(function(){{var t=document.getElementById('tip');
function show(e,el){{var p=(el.getAttribute('data-tip')||'').split('|');t.innerHTML='';p.forEach(function(s,i){{var n=document.createElement(i?'span':'b');n.textContent=s;t.appendChild(n);if(i)t.appendChild(document.createElement('br'))}});t.style.display='block';move(e)}}
function move(e){{var x=e.clientX+14,y=e.clientY+14,r=t.getBoundingClientRect();if(x+r.width>innerWidth-8)x=e.clientX-r.width-14;if(y+r.height>innerHeight-8)y=e.clientY-r.height-14;t.style.left=x+'px';t.style.top=y+'px'}}
document.querySelectorAll('.hit').forEach(function(el){{el.addEventListener('pointerenter',function(e){{show(e,el)}});el.addEventListener('pointermove',move);el.addEventListener('pointerleave',function(){{t.style.display='none'}})}});
}})();
</script></body></html>"""


def build(end: date | None = None, out_dir=None):
    data = analysis.analyze_week(end)
    out_dir = out_dir or config.REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    html_text = render(data)
    path = out_dir / f"weekly-{data['summary']['end']}.html"
    path.write_text(html_text, encoding="utf-8")
    (out_dir / "latest.html").write_text(html_text, encoding="utf-8")
    (out_dir / f"weekly-{data['summary']['end']}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return path


def main():
    from pathlib import Path
    ap = argparse.ArgumentParser(description="週次レポートを生成")
    ap.add_argument("--end", help="最終日 YYYY-MM-DD（省略時は今日）")
    ap.add_argument("--out", help="出力ディレクトリ")
    a = ap.parse_args()
    end = date.fromisoformat(a.end) if a.end else None
    print(build(end, Path(a.out) if a.out else None))


if __name__ == "__main__":
    main()
