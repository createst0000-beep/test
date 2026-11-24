"""設定値。環境変数で上書きできる。"""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MEAL_DATA_DIR", ROOT / "data"))
PHOTO_DIR = DATA_DIR / "photos"
DB_PATH = DATA_DIR / "meal_tracker.sqlite3"
REPORT_DIR = Path(os.environ.get("MEAL_REPORT_DIR", ROOT / "reports"))

TZ = ZoneInfo(os.environ.get("MEAL_TZ", "Asia/Tokyo"))

# 写真解析に使う Claude モデル
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

# 目標: 1か月で 2〜3kg 減
TARGET_LOSS_KG_PER_MONTH = (2.0, 3.0)
# 体脂肪 1kg ≒ 7,700kcal（Hall 2008 が単純化モデルとして示す値。実際は適応で目減りする）
KCAL_PER_KG_FAT = 7700

# プロフィール（筋肉維持チェックに使う）。体重はデータがあればそちらを優先
BODY_WEIGHT_KG = float(os.environ.get("BODY_WEIGHT_KG", "70"))
SEX = os.environ.get("SEX", "male")  # male / female

# リマインド時刻
REMINDER_TIMES = [(8, 0, "朝食"), (12, 0, "昼食"), (19, 0, "夕食"), (21, 0, "間食・飲み物")]
REPORT_TIME = (22, 0)

# 健康データ取り込み API の簡易トークン（スマホ自動化アプリから送るとき用）
INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "")


def ensure_dirs():
    for d in (DATA_DIR, PHOTO_DIR, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)
