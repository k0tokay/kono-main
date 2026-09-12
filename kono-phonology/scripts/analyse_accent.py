#!/usr/bin/env python3
"""測定結果から韻律仮説を検定する（手順 D の第一歩）.

    python3 scripts/analyse_accent.py --measure out/measure --key out/stimuli/stimuli_key.tsv

音節境界の自動推定は共鳴音の連続で誤りやすいので、ここでは
**音節分割に依存しない量**だけを使う:

- 目標語区間の f0 輪郭（時間正規化）
- 末尾 25% の傾き（半音/秒）と末尾の excursion → 語末上昇の有無
- f0 ピークの正規化位置 → プロミネンスがどこに置かれたか
- 目標語の持続時間 → 長音化・多音節短縮

要点: キャリア文では目標語は**発話末ではない**ので、語末の上昇 R が
語彙的なものか発話末の境界上昇かをここで切り分けられる．
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import parselmouth  # noqa: E402

from konophon import Word, inventory  # noqa: E402


def semitones(f, ref):
    return 12.0 * np.log2(np.asarray(f, dtype=float) / ref)


def build(measure_dir: Path, key_path: Path, audio: Path) -> pd.DataFrame:
    snd = parselmouth.Sound(str(audio))
    p = snd.to_pitch(time_step=0.005, pitch_floor=60, pitch_ceiling=400)
    pt = np.asarray(p.xs())
    pf = p.selected_array["frequency"].astype(float).copy()
    pf[pf == 0] = np.nan
    ok = np.isfinite(pf)
    PT, PF = pt[ok], pf[ok]

    tok = list(csv.DictReader((measure_dir / "tokens.tsv").open(encoding="utf-8"), delimiter="\t"))
    key = {}
    if key_path and key_path.exists():
        key = {r["単語"]: r for r in csv.DictReader(key_path.open(encoding="utf-8"), delimiter="\t")}

    inv = inventory()
    rows = []
    for t in tok:
        a, b = float(t["target_start"]), float(t["target_end"])
        d = b - a
        m = (PT >= a) & (PT <= b)
        tt, ff = PT[m], PF[m]
        if len(ff) < 6 or d <= 0:
            continue
        ref = float(np.median(ff))
        s = semitones(ff, ref)
        rel = (tt - a) / d
        tail = rel >= 0.75
        slope_end = float(np.polyfit(tt[tail], s[tail], 1)[0]) if tail.sum() >= 4 else np.nan
        k = max(2, int(0.10 * len(ff)))
        mid = len(ff) // 2
        exc_end = float(semitones(np.median(ff[-k:]), np.median(ff[max(0, mid - k) : mid + k])))
        w = Word(t["単語"], inv=inv)
        kk = key.get(t["単語"], {})
        rows.append(
            dict(
                order=int(t["order"]),
                word=t["単語"],
                syllabified=w.syllabified,
                n_syl=w.n_syllables,
                dur=d,
                dur_per_syl=d / w.n_syllables,
                carrier_score=float(t["carrier_score"]),
                slope_end_st_s=slope_end,
                exc_end_st=exc_end,
                peak_pos=float(rel[int(np.argmax(s))]),
                range_st=float(s.max() - s.min()),
                onset=kk.get("f_onset", ""),
                nucleus=kk.get("f_nucleus", ""),
                coda=kk.get("f_coda", ""),
                target_syl=kk.get("target", ""),
                block=kk.get("block", ""),
            )
        )
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--measure", type=Path, required=True)
    ap.add_argument("--key", type=Path, default=None)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    pd.set_option("display.width", 220)

    df = build(a.measure, a.key, a.audio)
    q = df[
        (df.carrier_score > df.carrier_score.quantile(0.05))
        & (df.dur_per_syl.between(0.12, 0.55))
    ]
    print(f"解析対象 {len(q)} / {len(df)} トークン（キャリア照合スコア下位5%と異常な長さを除外）\n")

    print("■ Q1 目標語の末尾は上がるか（句頭位置。発話末ではない）")
    print(f"   末尾25%の傾き 中央値 {q.slope_end_st_s.median():+.2f} 半音/秒")
    print(f"   上昇 (>+4 半音/秒) {(q.slope_end_st_s > 4).mean() * 100:5.1f}%")
    print(f"   下降 (<-4 半音/秒) {(q.slope_end_st_s < -4).mean() * 100:5.1f}%")
    print(f"   末尾 excursion 中央値 {q.exc_end_st.median():+.2f} 半音"
          f"  （上昇 >+1.5: {(q.exc_end_st > 1.5).mean() * 100:.1f}%  下降 <-1.5: {(q.exc_end_st < -1.5).mean() * 100:.1f}%）")
    print()
    print("■ Q2 f0 ピークの正規化位置（0=語頭, 1=語末）")
    print(q.groupby("n_syl").peak_pos.agg(["count", "median"]).round(3).to_string())
    print()
    for blk, col, title in (
        ("onset", "onset", "Q3 オンセット型（他因子は baseline）"),
        ("coda", "coda", "Q4 コーダ型"),
        ("nucleus", "nucleus", "Q5 核の型"),
    ):
        sub = q[q.block == blk]
        if sub.empty:
            continue
        print(f"■ {title}")
        print(
            sub.groupby(col)
            .agg(n=("word", "size"), dur_per_syl=("dur_per_syl", "median"),
                 peak=("peak_pos", "median"), range_st=("range_st", "median"))
            .round(3)
            .to_string()
        )
        print()
    print("■ Q6 目標語長 ~ 音節数")
    print(q.groupby("n_syl").agg(n=("word", "size"), dur=("dur", "median"),
                                 per_syl=("dur_per_syl", "median")).round(3).to_string())
    out = a.out or (a.measure / "token_f0.tsv")
    df.to_csv(out, sep="\t", index=False)
    print(f"\n[出力] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
