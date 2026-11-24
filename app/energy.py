"""ウェアラブルを着けていない時間の運動の消費カロリー推定。

1日の消費（Fit・SOXAI）にはその時間の安静時代謝が既に入っているので、
ここでは「上乗せ分」＝ (MET − 1) × 体重 × 時間 を返す（二重計上を避ける）。
MET は Compendium of Physical Activities（Ainsworth 2011）の値。
"""

# 筋トレ（複数種目・8〜15回・セット間休憩込み）: 3.5 MET。
# 高重量・高強度のボディビル系は 6.0 MET だが、休憩の長い減量中のトレーニングでは過大になりやすいので控えめな値を使う。
STRENGTH_MET = 3.5
MIN_PER_SET = 3.0  # 時間が無いときの目安（1セット＋休憩）


def strength_kcal(weight_kg: float, minutes: float | None = None, sets: int | None = None) -> int | None:
    if not minutes and sets:
        minutes = sets * MIN_PER_SET
    if not minutes:
        return None
    return round((STRENGTH_MET - 1) * weight_kg * minutes / 60)


def treadmill_walk_kcal(weight_kg: float, minutes: float, speed_kmh: float, incline_pct: float = 0) -> int:
    """ACSM の歩行式: VO2 = 0.1·S + 1.8·S·G + 3.5（S: m/分、G: 傾斜）。上乗せ分だけ返す。"""
    s = speed_kmh * 1000 / 60
    vo2_net = 0.1 * s + 1.8 * s * incline_pct / 100  # ml/kg/分（安静分 3.5 を除く）
    return round(vo2_net * weight_kg / 1000 * 5 * minutes)
