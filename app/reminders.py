"""リマインダー: カレンダー（.ics）と Web Push 通知。

.ics は毎日 7:00 / 12:00 / 19:00 / 21:00 の繰り返し予定に、音つきアラーム（AUDIO）と画面通知（DISPLAY）を
付けたもの。Google カレンダー／iPhone カレンダーに読み込むと端末の通知音・バイブで鳴る。
"""
import json
from datetime import datetime

from . import config

PUSH_SUBS_FILE = config.DATA_DIR / "push_subscriptions.json"
VAPID_FILE = config.DATA_DIR / "vapid.json"


def build_ics(app_url: str = "") -> str:
    today = datetime.now(config.TZ).strftime("%Y%m%d")
    tz = str(config.TZ)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//meal-tracker//JP", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:食事写真リマインド", f"X-WR-TIMEZONE:{tz}"]
    times = [(h, m, f"{label}の写真を送る") for h, m, label in config.REMINDER_TIMES]
    times.append((*config.REPORT_TIME, "週間レポートを確認"))
    for h, m, title in times:
        uid = f"meal-reminder-{h:02d}{m:02d}@meal-tracker"
        desc = f"アプリを開いて撮影: {app_url}" if app_url else "食事・飲み物の写真を撮って登録"
        lines += [
            "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{today}T000000Z",
            f"DTSTART;TZID={tz}:{today}T{h:02d}{m:02d}00", "DURATION:PT10M",
            "RRULE:FREQ=DAILY", f"SUMMARY:📸 {title}", f"DESCRIPTION:{desc}",
            *( [f"URL:{app_url}"] if app_url else [] ),
            "BEGIN:VALARM", "ACTION:AUDIO", "TRIGGER:PT0M", "END:VALARM",
            "BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:PT0M", f"DESCRIPTION:{title}", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# ------------------------------------------------------------------ Web Push
def vapid_keys():
    """VAPID 鍵を（なければ生成して）返す。"""
    config.ensure_dirs()
    if VAPID_FILE.exists():
        return json.loads(VAPID_FILE.read_text())
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    priv = base64.urlsafe_b64encode(key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())).decode().rstrip("=")
    pub = key.public_key().public_bytes(serialization.Encoding.X962,
                                        serialization.PublicFormat.UncompressedPoint)
    keys = {"private": priv, "public": base64.urlsafe_b64encode(pub).decode().rstrip("=")}
    VAPID_FILE.write_text(json.dumps(keys))
    return keys


def save_subscription(sub: dict):
    subs = load_subscriptions()
    if sub not in subs:
        subs.append(sub)
    PUSH_SUBS_FILE.write_text(json.dumps(subs))


def load_subscriptions():
    return json.loads(PUSH_SUBS_FILE.read_text()) if PUSH_SUBS_FILE.exists() else []


def send_push(title: str, body: str, url: str = "/", tag: str = "meal"):
    """登録済みの全端末に通知を送る。音とバイブは端末の通知設定に従う（sw.js で vibrate を指定）。"""
    subs = load_subscriptions()
    if not subs:
        return 0
    from pywebpush import WebPushException, webpush
    keys = vapid_keys()
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag}, ensure_ascii=False)
    alive, sent = [], 0
    for s in subs:
        try:
            webpush(s, payload, vapid_private_key=keys["private"],
                    vapid_claims={"sub": "mailto:meal-tracker@localhost"}, ttl=3600)
            alive.append(s)
            sent += 1
        except WebPushException as e:
            if e.response is None or e.response.status_code not in (404, 410):
                alive.append(s)  # 一時的な失敗は保持、失効（404/410）は削除
    PUSH_SUBS_FILE.write_text(json.dumps(alive))
    return sent
