"""食事写真から品目・カロリー・PFC を推定する（Claude API）。"""
import base64
import json
import mimetypes
import os
import re

from . import config

PROMPT = """あなたは管理栄養士です。写真の食事・飲み物を品目ごとに分け、日本食品標準成分表（八訂）の値を目安に1人前の栄養量を推定してください。
- 量が分かる手がかり（器の大きさ、箸、パッケージ表示）があれば使う。パッケージの栄養成分表示が写っていればそれを優先。
- 飲み物も必ず1品目にする（水・お茶・ブラックコーヒーは0kcal）。アルコールは純アルコール量(g)も推定。
- ultra_processed は NOVA分類4（菓子・菓子パン・カップ麺・加工肉・清涼飲料など）なら true。
{hint}
JSON だけを返すこと（前後に文章を付けない）:
{{"items":[{{"name":"品名","kind":"food|drink","amount":"量の目安","kcal":0,"protein_g":0,"fat_g":0,"carb_g":0,"fiber_g":0,"salt_g":0,"alcohol_g":0,"ultra_processed":false}}],
"confidence":"high|medium|low","comment":"推定の前提や不確かな点を一言"}}"""


def analyze_photo(path, note: str | None = None):
    """写真を解析して dict を返す。ANTHROPIC_API_KEY が無い場合は空の結果を返す（手入力で補正可）。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"items": [], "confidence": "none", "comment": "ANTHROPIC_API_KEY 未設定のため自動推定をスキップしました。"}
    import anthropic

    media = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.standard_b64encode(open(path, "rb").read()).decode()
    hint = f"- 本人のメモ: {note}" if note else ""
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
            {"type": "text", "text": PROMPT.format(hint=hint)},
        ]}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    return parse_json(text)


def parse_json(text: str):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON が見つかりません: {text[:200]}")
    obj = json.loads(m.group(0))
    items = []
    for it in obj.get("items", []):
        clean = {"name": str(it.get("name", "不明")), "kind": "drink" if it.get("kind") == "drink" else "food",
                 "amount": str(it.get("amount", "")), "ultra_processed": bool(it.get("ultra_processed"))}
        for k in ("kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "salt_g", "alcohol_g"):
            try:
                clean[k] = max(0.0, float(it.get(k) or 0))
            except (TypeError, ValueError):
                clean[k] = 0.0
        items.append(clean)
    return {"items": items, "confidence": obj.get("confidence", "medium"), "comment": obj.get("comment", "")}
