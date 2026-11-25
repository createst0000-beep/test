"""判定ルールの根拠となる文献。レポートの注意点にはここの ID を付けて出典を明示する。"""

SOURCES = {
    # ---- 特に重視する情報源（利用者の希望）: バズーカ岡田（岡田隆・日本体育大学教授） ----
    # 具体的な主張を判定に使うときは、確認した動画 URL や書名・該当箇所を別エントリとして追加する。
    "okada_youtube": {
        "cite": "岡田隆（バズーカ岡田）公式 YouTube「新・バズーカ岡田チャンネル」",
        "url": "https://www.youtube.com/@bazooka_okada",
        "point": "除脂肪（減量）と筋肉維持の実践的な方法についての公式発信。特に重要な参考文献として扱う。",
    },
    "okada_book_jyoshibou": {
        "cite": "岡田隆『除脂肪メソッド』",
        "url": "",
        "point": "筋肉を残して体脂肪を落とすための食事とトレーニングの方法をまとめた代表作。",
    },
    "okada_book_muteki": {
        "cite": "岡田隆『無敵の筋トレ食』ポプラ社, 2022",
        "url": "https://www.maruzenjunkudo.co.jp/products/9784591172483",
        "point": "筋トレをする人の食事の選び方。",
    },
    "hall2008": {
        "cite": "Hall KD. What is the required energy deficit per unit weight loss? Int J Obes. 2008;32:573-576.",
        "url": "https://doi.org/10.1038/sj.ijo.0803720",
        "point": "体重1kg減≒約7,700kcalは初期の目安。代謝適応で必要な不足量は時間とともに増える。",
    },
    "helms2014": {
        "cite": "Helms ER, Aragon AA, Fitschen PJ. Evidence-based recommendations for natural bodybuilding contest preparation: nutrition and supplementation. J Int Soc Sports Nutr. 2014;11:20.",
        "url": "https://doi.org/10.1186/1550-2783-11-20",
        "point": "筋量を守るなら減量ペースは体重の0.5〜1%/週。減量中のたんぱく質は除脂肪体重あたり2.3〜3.1g/kg。",
    },
    "garthe2011": {
        "cite": "Garthe I, et al. Effect of two different weight-loss rates on body composition and strength and power-related performance in elite athletes. Int J Sport Nutr Exerc Metab. 2011;21:97-104.",
        "url": "https://doi.org/10.1123/ijsnem.21.2.97",
        "point": "週0.7%のゆっくり減量群は除脂肪量を維持・増加、週1.4%群は筋力向上が乏しかった。",
    },
    "murphy2022": {
        "cite": "Murphy C, Koehler K. Energy deficiency impairs resistance training gains in lean mass but not strength: a meta-analysis and meta-regression. Scand J Med Sci Sports. 2022;32:125-137.",
        "url": "https://doi.org/10.1111/sms.14075",
        "point": "1日約500kcalを超えるエネルギー不足では筋トレによる除脂肪量の増加が阻害されやすい。",
    },
    "morton2018": {
        "cite": "Morton RW, et al. A systematic review, meta-analysis and meta-regression of the effect of protein supplementation on resistance training-induced gains in muscle mass and strength. Br J Sports Med. 2018;52:376-384.",
        "url": "https://doi.org/10.1136/bjsports-2017-097608",
        "point": "筋量増加の効果は約1.6g/kg/日で頭打ち（95%信頼区間の上限2.2g/kg）。",
    },
    "longland2016": {
        "cite": "Longland TM, et al. Higher compared with lower dietary protein during an energy deficit combined with intense exercise promotes greater lean mass gain and fat mass loss. Am J Clin Nutr. 2016;103:738-746.",
        "url": "https://doi.org/10.3945/ajcn.115.119339",
        "point": "大きなエネルギー不足下でも2.4g/kg/日＋高強度トレーニングで除脂肪量が増え、脂肪がより減った。",
    },
    "jager2017": {
        "cite": "Jäger R, et al. International Society of Sports Nutrition Position Stand: protein and exercise. J Int Soc Sports Nutr. 2017;14:20.",
        "url": "https://doi.org/10.1186/s12970-017-0177-8",
        "point": "運動者は1.4〜2.0g/kg/日。1食20〜40g、3〜4時間おきに分けて摂るのがよい。",
    },
    "schoenfeld2018": {
        "cite": "Schoenfeld BJ, Aragon AA. How much protein can the body use in a single meal for muscle-building? J Int Soc Sports Nutr. 2018;15:10.",
        "url": "https://doi.org/10.1186/s12970-018-0215-1",
        "point": "1食0.4g/kgを1日4食以上（合計1.6g/kg以上）が筋合成を最大化する目安。",
    },
    "schoenfeld2016freq": {
        "cite": "Schoenfeld BJ, Ogborn D, Krieger JW. Effects of resistance training frequency on measures of muscle hypertrophy: a systematic review and meta-analysis. Sports Med. 2016;46:1689-1697.",
        "url": "https://doi.org/10.1007/s40279-016-0543-8",
        "point": "各部位を週2回以上鍛えるほうが週1回より筋肥大に有利。",
    },
    "schoenfeld2017vol": {
        "cite": "Schoenfeld BJ, Ogborn D, Krieger JW. Dose-response relationship between weekly resistance training volume and increases in muscle mass. J Sports Sci. 2017;35:1073-1082.",
        "url": "https://doi.org/10.1080/02640414.2016.1210197",
        "point": "部位ごとに週10セット以上で筋量増加が大きい。",
    },
    "wilson2012": {
        "cite": "Wilson JM, et al. Concurrent training: a meta-analysis examining interference of aerobic and resistance exercises. J Strength Cond Res. 2012;26:2293-2307.",
        "url": "https://doi.org/10.1519/JSC.0b013e31823a3e2d",
        "point": "有酸素運動は頻度・時間が多いほど筋トレ効果を干渉。ランニングは自転車より干渉が大きい。",
    },
    "nedeltcheva2010": {
        "cite": "Nedeltcheva AV, et al. Insufficient sleep undermines dietary efforts to reduce adiposity. Ann Intern Med. 2010;153:435-441.",
        "url": "https://doi.org/10.7326/0003-4819-153-7-201010050-00006",
        "point": "同じカロリー制限でも睡眠5.5時間では8.5時間に比べ脂肪の減少が55%少なく、除脂肪量の減少が60%多かった。",
    },
    "parr2014": {
        "cite": "Parr EB, et al. Alcohol ingestion impairs maximal post-exercise rates of myofibrillar protein synthesis following a single bout of concurrent training. PLoS One. 2014;9:e88384.",
        "url": "https://doi.org/10.1371/journal.pone.0088384",
        "point": "運動後の大量飲酒は、たんぱく質を一緒に摂っても筋たんぱく合成を24〜37%低下させた。",
    },
    "hall2019": {
        "cite": "Hall KD, et al. Ultra-processed diets cause excess calorie intake and weight gain. Cell Metab. 2019;30:67-77.",
        "url": "https://doi.org/10.1016/j.cmet.2019.05.008",
        "point": "超加工食品中心の食事では自由摂取で1日約500kcal多く食べてしまった。",
    },
    "shcherbina2017": {
        "cite": "Shcherbina A, et al. Accuracy in wrist-worn, sensor-based measurements of heart rate and energy expenditure in a diverse cohort. J Pers Med. 2017;7:3.",
        "url": "https://doi.org/10.3390/jpm7020003",
        "point": "ウェアラブルの消費カロリーは誤差が大きく、誤差20%未満の機器はなかった。",
    },
    "paluch2022": {
        "cite": "Paluch AE, et al. Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts. Lancet Public Health. 2022;7:e219-e228.",
        "url": "https://doi.org/10.1016/S2468-2667(21)00302-9",
        "point": "60歳未満では1日8,000〜10,000歩まで歩数が多いほど死亡リスクが低下した。",
    },
    "ainsworth2011": {
        "cite": "Ainsworth BE, et al. 2011 Compendium of Physical Activities: a second update of codes and MET values. Med Sci Sports Exerc. 2011;43:1575-1581.",
        "url": "https://doi.org/10.1249/MSS.0b013e31821ece12",
        "point": "筋トレ（複数種目・8〜15回）は3.5 MET、高強度のボディビル系は6.0 MET。ジムでの消費の推定に使用。",
    },
    "mhlw_dri2020": {
        "cite": "厚生労働省「日本人の食事摂取基準（2020年版）」",
        "url": "https://www.mhlw.go.jp/stf/newpage_08517.html",
        "point": "食塩相当量の目標量は男性7.5g未満・女性6.5g未満。食物繊維の目標量は18〜64歳の男性21g以上・女性18g以上。",
    },
    "mhlw_alcohol": {
        "cite": "厚生労働省 e-ヘルスネット「飲酒のガイドライン」／健康日本21",
        "url": "https://www.e-healthnet.mhlw.go.jp/information/alcohol/a-03-003.html",
        "point": "「節度ある適度な飲酒」は純アルコールで1日平均約20g程度。",
    },
}


def cite_list(ids):
    """ID のリストから表示用の出典リストを返す（重複は除く）。"""
    seen, out = set(), []
    for i in ids:
        if i in SOURCES and i not in seen:
            seen.add(i)
            out.append({"id": i, **SOURCES[i]})
    return out
