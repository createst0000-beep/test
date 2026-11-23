"""毎日の定時処理: 7/12/19/21時のリマインド通知、22時の週次レポート生成。"""
import logging
import os
import threading
import time
from datetime import datetime

from . import config, report, reminders

log = logging.getLogger("scheduler")


def _job_reminder(label):
    n = reminders.send_push(f"📸 {label}の写真を送ってください",
                            "撮影して登録 → 自動でカロリーとたんぱく質を推定します", url="/?slot=" + label,
                            tag="meal-reminder")
    log.info("reminder %s sent to %d devices", label, n)


def _job_report():
    if os.environ.get("GOOGLE_CLIENT_ID") and (config.DATA_DIR / "google_fit_token.json").exists():
        try:
            from . import health
            health.fetch_google_fit(days=8)
        except Exception as e:  # Fit API 終了後も止まらないように
            log.warning("google fit fetch failed: %s", e)
    path = report.build()
    log.info("report written: %s", path)
    reminders.send_push("📊 今週のレポートができました", "カロリー収支・たんぱく質・運動の振り返り",
                        url="/report", tag="weekly-report")


def run_forever():
    jobs = {(h, m): (lambda l=label: _job_reminder(l)) for h, m, label in config.REMINDER_TIMES}
    jobs[config.REPORT_TIME] = _job_report
    last = None
    while True:
        now = datetime.now(config.TZ)
        key = (now.hour, now.minute)
        if key in jobs and key != last:
            last = key
            try:
                jobs[key]()
            except Exception:
                log.exception("job failed at %s", key)
        elif key not in jobs:
            last = None
        time.sleep(20)


def start_background():
    t = threading.Thread(target=run_forever, daemon=True, name="scheduler")
    t.start()
    return t
