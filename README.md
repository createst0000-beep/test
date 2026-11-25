# 食事写真 × Fit／SOXAI カロリー収支トラッカー

毎日の食事を写真で記録し、Fit／SOXAI RING の消費カロリーと合わせて **1日の総カロリー（摂取 − 消費）をマイナスに保つ** ためのアプリです。
目標は **1か月に 2〜3kg 減**。筋トレをしている前提で、**筋肉を落とさない**ための判定（たんぱく質、減量ペース、筋トレの頻度とセット数、睡眠、飲酒）も文献に基づいて行います。

| 機能 | 内容 |
|---|---|
| 写真で記録 | スマホで撮影 → Claude が品目・kcal・PFC・食物繊維・塩分・アルコール量を推定 |
| 消費データ | Google Fit REST API／ヘルスコネクト経由の送信（SOXAI RING）／CSV／手入力 |
| リマインド | 8:00／12:00／19:00／21:00 に、プッシュ通知（音とバイブ）、カレンダー通知、時計アプリのアラームで知らせる |
| 週次レポート | 毎日 22:00 に直近 7 日分のグラフ付き HTML を生成（`/report`、`reports/latest.html`）し、完成を通知 |

サンプル: [`reports/sample/weekly-2026-11-22.html`](reports/sample/weekly-2026-11-22.html)（デモデータ）

> **現在の運用は claude.ai 上で完結しています**（サーバー・API キー不要）。記録は claude.ai の「食事写真ログ」ページ、レポートはそのページの「週間レポート」タブ（リアルタイム）と、毎日22時に更新される「週間カロリーレポート」ページです。仕様・目標値・計算ルール・自動更新の設定は [CLAUDE.md](CLAUDE.md) にまとめています。以下の Flask サーバー版は、自前で動かしたい場合の代替手段です。

## 目標の数値と根拠

| 項目 | 目標 | 根拠 |
|---|---|---|
| 1日の収支 | **−513〜−770 kcal**（月 2〜3kg × 7,700kcal ÷ 30日）。筋トレ中は −500 前後が安全 | Hall 2008; Murphy & Koehler 2022（約 500kcal を超える不足は筋量の増加を妨げやすい） |
| 減量ペース | 体重の **週 0.5〜1%** まで | Helms 2014; Garthe 2011 |
| たんぱく質 | **1.6g/kg 以上**、減量中は **2.0〜2.4g/kg** | Morton 2018; Longland 2016; ISSN 2017 |
| たんぱく質の配分 | 1食 **0.4g/kg** を 3〜4 回 | Schoenfeld & Aragon 2018 |
| 筋トレ | 各部位を **週 2 回以上**、**週 10 セット以上** | Schoenfeld 2016, 2017 |
| 有酸素 | 消費を増やすなら歩数・自転車を優先（ランニングは筋トレとの干渉が大きい） | Wilson 2012; Paluch 2022 |
| 睡眠 | **7 時間以上**（5.5 時間だと除脂肪量の減少が 60% 増えた） | Nedeltcheva 2010 |
| 飲酒 | 1日 20g 以内。筋トレの日は控える（筋たんぱく合成が 24〜37% 低下） | 厚労省; Parr 2014 |
| 塩分・食物繊維 | 食塩 7.5g 未満（女性 6.5g）、食物繊維 21g 以上（女性 18g） | 日本人の食事摂取基準 2020 |
| 加工食品・飲み物 | 超加工食品と、カロリーのある飲み物の割合を監視 | Hall 2019 |
| ウェアラブルの誤差 | 消費カロリーは 20% 以上ずれることがあるので、体重の推移で答え合わせ | Shcherbina 2017 |

全文献（DOI リンク付き）は `app/evidence.py` にまとめてあり、レポートの各注意点からも開けます。

## セットアップ

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...   # 写真解析に使う
export BODY_WEIGHT_KG=72 SEX=male     # たんぱく質の目標計算に使う（体重の記録があればそちらを優先）
export INGEST_TOKEN=好きな長い文字列     # 外部に公開する場合は必ず設定

python -m app.server                  # http://0.0.0.0:8000 で起動。スケジューラも同時に起動する
```

- スマホから使うには、サーバーに **HTTPS** で届く必要があります（例: 自宅 PC と Tailscale、または小さなクラウド VM）。
- サーバーを常時起動しておくと、7/12/19/21 時のリマインド通知と、22 時のレポート生成が自動で動きます。
- cron を使う場合は、`DISABLE_SCHEDULER=1` で起動して次を登録します: `0 22 * * * cd /path && .venv/bin/python -m app.report`

スマホ側の設定（通知・アラーム・Fit／SOXAI 連携）: **[docs/phone_setup.md](docs/phone_setup.md)**

## 主なエンドポイント

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/` | 撮影・記録画面（PWA） |
| POST | `/api/meals` | 写真（`photo`）・`slot`・`note` → 推定して保存 |
| PUT/DELETE | `/api/meals/<id>` | 推定結果の修正・削除 |
| POST | `/api/health` | 日別の消費・歩数・睡眠・体重・運動（JSON） |
| POST | `/api/health/csv` | 上と同じ内容を CSV で |
| POST | `/api/workouts` | 筋トレの部位・セット数 |
| GET | `/report?end=YYYY-MM-DD` | 週次レポート（HTML） |
| GET | `/api/week` | 週次の分析結果（JSON） |
| GET | `/reminders.ics` | リマインドのカレンダー |

## 開発

```bash
python -m pytest -q
MEAL_DATA_DIR=/tmp/demo python scripts/seed_demo.py 2026-11-22   # デモデータを投入
MEAL_DATA_DIR=/tmp/demo python -m app.report --end 2026-11-22
```

> 写真からのカロリー推定にもウェアラブルの消費カロリーにも誤差があります。体重の週平均の推移と合わせて判断してください。持病がある場合は医師・管理栄養士に相談してください。
