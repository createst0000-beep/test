# 食事写真 × Fit／SOXAI カロリー収支トラッカー（運用メモ）

Claude が作業を引き継ぐときの前提をまとめたファイル。利用者向けの説明は README.md、スマホ側の設定は docs/phone_setup.md。

## 1. 目的
- 毎日の食事を写真で記録し、Fit／SOXAI RING の消費カロリーと合わせて **1日の収支（摂取 − 消費）をマイナス** に保つ。
- 目標は **1か月 2〜3kg 減**。利用者は筋トレをしているので、**筋肉を落とさない** ことも同じくらい重視する。
- 指示やアドバイスは、`app/evidence.py` にある文献を根拠にする（新しい判定を足すときも出典を付ける）。

## 2. 現在の運用（claude.ai 上で完結。サーバー・API キー不要）

| もの | URL | 役割 |
|---|---|---|
| 記録ページ「食事写真ログ」 | https://claude.ai/artifact/3HUAV7ay7hQkh7jh9RpXBk | 写真・スクショ・筋トレの記録。データベース（db）を持つ。「週間レポート」タブ（`#report`）は db から **常にリアルタイム** で集計 |
| 週間カロリーレポート | https://claude.ai/artifact/6URYrjzRKPH3AENWu1tth8 | 静的な HTML。毎日22時と、チャットで記録を変更したときに Claude が作り直す |

- 記録ページのソース: `artifacts/meal-log.html`（公開版と同じ内容に保つ。変更したら再公開＋コミット）。
- 記録ページの capabilities: `db`、`sample`（images: true。写真解析を claude.ai のプランで実行）、`assets`（写真保存）。
- 両ページとも利用者本人だけが開ける（非公開）。

### データベースの形（記録ページの db）
| コレクション | ドキュメント ID | 主なフィールド |
|---|---|---|
| `meals` | 自動 ID、またはチャット登録分は `chat-YYYY-MM-DD-<区分>` | `date`, `time`, `slot`（朝食/昼食/夕食/間食・飲み物/朝兼昼食 など）, `items[]`（name, kind=food/drink, amount, kcal, protein_g, fat_g, carb_g, fiber_g, salt_g, alcohol_g, ultra_processed）, 各合計値, `confidence`, `comment`, `photo_id` |
| `health` | `YYYY-MM-DD` | `total_burn_kcal`（採用値）, `burn_fit_kcal`, `burn_soxai_kcal`, `active_kcal`, `bmr_kcal`, `steps`, `steps_fit`, `sleep_min`, `weight_kg`, `sources[]`, `note` |
| `workouts` | 自動 ID または `chat-YYYY-MM-DD-<種目>` | `date`, `type`（strength/walking/running/cycling/other…）, `name`, `minutes`, `sets`, `muscle_groups[]`（chest/back/legs/shoulders/arms/glutes/core）, `kcal`, `add_to_burn` |
| `settings` | `profile` | `body_weight_kg`（現在 75）, `sex`（male）, `bmr_kcal` |

既存ドキュメントへの書き込みは、読んだ `version` を `if_version` に付ける。別の会話の Claude も同じ db を更新することがあるので、上書き前に必ず読み直す。

## 3. 目標値と計算ルール

| 項目 | 値 | 根拠・メモ |
|---|---|---|
| 1日の収支 | **−513〜−770 kcal**（2〜3kg × 7,700kcal ÷ 30日） | Hall 2008。筋トレ中は −500 前後が安全（Murphy 2022） |
| 収支の警告 | −1,000 kcal より大きいと「要改善」 | 週1%超の減量は筋力低下（Helms 2014, Garthe 2011） |
| たんぱく質 | 最低 1.6 g/kg（120g）、減量中の目安 **2.0 g/kg（150g）**、上限目安 2.4 | Morton 2018, Longland 2016, ISSN 2017 |
| 1食のたんぱく質 | 0.4 g/kg（30g）を 3〜4 回 | Schoenfeld & Aragon 2018 |
| 筋トレ | 各部位 週2回以上・週10セット以上 | Schoenfeld 2016, 2017 |
| 有酸素 | ランニングより歩行・傾斜ウォーク | Wilson 2012 |
| 歩数 | 8,000〜10,000 歩 | Paluch 2022 |
| 睡眠 | 7時間以上 | Nedeltcheva 2010 |
| 飲酒 | 純アルコール 20g/日 以内、筋トレ日は控えめ | 厚労省、Parr 2014 |
| 塩分・食物繊維 | 食塩 7.5g 未満、食物繊維 21g 以上（男性） | 日本人の食事摂取基準 2020 |

### 計算の決まりごと
- **消費カロリーは Fit と SOXAI の低い方** を `total_burn_kcal` に採用（ウェアラブルの誤差 20%超: Shcherbina 2017）。もう一方も別フィールドに残す。
- **ジム中はリングも Fit も着けていない**。ジムの運動は `add_to_burn: true` にし、その `kcal` を1日の消費に上乗せする。
  - 筋トレ: (3.5 MET − 1) × 体重 × 時間。時間不明なら 1セット3分（75kg なら 3セット ≒ 28kcal）。`app/energy.py`、Compendium 2011。
  - マシン有酸素: マシン表示から安静分（約 1.3 kcal/分）を引いた値。傾斜ウォークは ACSM 歩行式でも可。
- **21時前の当日は「集計中」** とし、週の平均には入れない。
- 塩分・食物繊維の平均は、品目の内訳がある日だけで計算する。
- 体重はその週の最新記録、無ければ `settings/profile` の値を使う。
- 写真やパッケージの栄養成分表示があれば、それを優先して記録する。推定のときは `comment` に前提（量、スープを飲んだか等）を書く。

## 4. 自動更新・通知の設定

| 内容 | 設定 |
|---|---|
| 22時のレポート更新 | 定時タスク `trig_01SrzKpVSDDKeJxvmh5fMAcQ`「週間カロリーレポート（毎日22時）」。`CRON_TZ=Asia/Tokyo 0 22 * * *`、実行ごとに新しいセッション、完了時にスマホへプッシュ通知。手順: db を書き出し → `scripts/report_from_artifact.py` → 週間カロリーレポートに公開。このブランチのコードを使うので、変更は push しておく |
| チャットで記録したとき | db を更新したら、週間カロリーレポートも作り直して公開する（利用者の依頼） |
| 撮影リマインド | **8:00／12:00／19:00／21:00**（＋22:00 レポート確認）。`docs/meal-reminders.ics`（UID は区分ごとに固定）をカレンダーに取り込む。スマホの時計アラームは利用者が手動で設定（手順は docs/phone_setup.md） |
| 時刻の変更 | `app/config.py` の `REMINDER_TIMES` を変え、.ics を作り直して送る |

### レポートを手動で作り直す手順
1. ArtifactData で `meals` / `health` / `workouts` を `date >= 開始日（今日−6日）` で query、`settings/profile` を get。すべて `out_dir=<scratchpad>/export` に保存（古い export は先に消す）。
2. `TZ=Asia/Tokyo python3 scripts/report_from_artifact.py <scratchpad>/export --end <今日> --out <scratchpad>/rep`
3. `<scratchpad>/rep/artifact.html` を週間カロリーレポートの URL に公開（別セッションが更新していれば先に read）。

## 5. ファイル構成

```
CLAUDE.md                     この運用メモ
README.md                     利用者向けの説明（目標と根拠、セットアップ）
artifacts/meal-log.html       記録ページ（claude.ai Artifact）のソース。週間レポートタブの JS 版集計を含む
scripts/report_from_artifact.py  記録ページの db 書き出し → 週次レポート HTML（artifact.html も出力）
scripts/seed_demo.py          デモデータ投入
app/
  config.py                   目標値・リマインド時刻・タイムゾーン
  analysis.py                 週次集計と判定ルール（JS 版は artifacts/meal-log.html にある。変更は両方に）
  evidence.py                 根拠文献（DOI 付き）
  energy.py                   ジムの消費推定（MET・ACSM 歩行式）
  report.py                   レポート HTML（インライン SVG のグラフ）
  db.py                       SQLite（レポート生成時の一時 DB にも使用）
  health.py                   消費・運動データの取り込み（JSON／CSV／Google Fit REST）
  reminders.py                .ics 生成、Web Push
  vision.py / server.py / scheduler.py / fit_auth.py / templates / static
                              自前サーバー版（Flask の PWA。現在は未使用の代替手段）
docs/phone_setup.md           スマホ側の設定（通知・アラーム・Fit／SOXAI 連携）
docs/meal-reminders.ics       リマインドのカレンダー
reports/sample/               デモデータのレポート例
tests/test_app.py             pytest（`python -m pytest -q`）
```

## 6. 注意
- 判定ルールは Python（`app/analysis.py`）と JS（`artifacts/meal-log.html` の週間レポート部分）の2か所にある。片方だけ変えない。
- Google Fit API は 2026 年中に終了予定。ヘルスコネクトはクラウド API が無く、SOXAI にも公開 API は無い。そのため消費データは **スクショ読み取り** で取り込んでいる。
- 利用者の個人情報や記録内容を外部サービスに送らない。
