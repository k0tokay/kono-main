#!/usr/bin/env python3
"""統制された nonce 語の刺激セットを生成する（手順 B）.

出力:

``stimuli_key.tsv``
    設計行列（因子水準・意図した音節化）．**判断中は見ないこと**．
``stimuli_blind.tsv``
    判断・録音用．シャッフル済み・設計情報なし・反復項目入り．
    列名は ``accent/data.tsv`` と揃えてあるのでそのまま追記できる．
``stimuli_balance.tsv``
    因子水準ごとの件数（設計のバランス確認用）．

使い方:

    python3 scripts/gen_stimuli.py --out-dir out/stimuli --seed 42 \\
        --lexicon ../kono-dictionary-editor/src/data/konomeno-v5.json --anchors 8

録音の手順（この順番が重要）:

1. まず ``stimuli_blind.tsv`` の順に **仮説を議論する前に** 通しで読み上げて録音する
2. 読みながら「高低」列だけを埋める（音節化は後で音声から決める）
3. 反復項目の一致率を見る＝自分の判断の再現率
4. その後で Praat 等で f0 と母音長を測る（手順 C）
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from konophon import Grammar, inventory  # noqa: E402
from konophon.corpus import autoload  # noqa: E402
from konophon.stimuli import balance_report, blind_order, generate  # noqa: E402

ALL_BLOCKS = ["core", "onset", "coda", "nucleus", "position", "length"]


def write_tsv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="out/stimuli", type=Path)
    ap.add_argument("--blocks", default=",".join(ALL_BLOCKS), help=f"生成ブロック: {ALL_BLOCKS}")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--repeat-rate", type=float, default=0.10, help="反復して信頼性を測る項目の割合")
    ap.add_argument("--anchors", type=int, default=0, help="既知語を錨として混ぜる件数")
    ap.add_argument("--lexicon", type=Path, default=None, help="既存語との衝突を避けるための辞書")
    ap.add_argument("--limit", type=int, default=0, help="0 以外なら先頭 N 件に切る")
    a = ap.parse_args(argv)

    inv = inventory()
    lex_words: list[str] = []
    if a.lexicon:
        c = autoload(a.lexicon, inv)
        lex_words = [w.spell for w in c]
        print(f"[辞書] {a.lexicon} から {len(lex_words)} 語（衝突回避用）")

    stimuli, report = generate(
        blocks=[b.strip() for b in a.blocks.split(",") if b.strip()],
        inv=inv,
        lexicon=lex_words,
        grammar=Grammar.from_inventory(inv),
    )
    if a.limit:
        stimuli = stimuli[: a.limit]

    print(f"[生成] {report.summary()}")
    if report.dropped_resyllabified:
        print(f"  ! MOP で別構造に再解析されたため除外した設計 {len(report.dropped_resyllabified)} 件:")
        for design, pos, actual in report.dropped_resyllabified[:10]:
            print(f"      {design} (n_syl,target={pos}) → 実際は {actual}")
        if len(report.dropped_resyllabified) > 10:
            print(f"      ... 他 {len(report.dropped_resyllabified) - 10} 件")

    import random

    anchors: list[str] = []
    if a.anchors and lex_words:
        anchors = random.Random(a.seed).sample(lex_words, min(a.anchors, len(lex_words)))

    out = a.out_dir
    write_tsv(out / "stimuli_key.tsv", [s.as_key_row() for s in stimuli])
    write_tsv(out / "stimuli_blind.tsv", blind_order(
        stimuli, seed=a.seed, repeat_rate=a.repeat_rate, anchors=anchors
    ))
    bal = balance_report(stimuli)
    if not bal.empty:
        write_tsv(out / "stimuli_balance.tsv", bal.to_dict("records"))
        print("\n[バランス]")
        print(bal.to_string(index=False))

    blind_n = sum(1 for _ in (out / "stimuli_blind.tsv").read_text(encoding="utf-8").splitlines()) - 1
    print(f"\n[出力] {out}/stimuli_key.tsv     ({len(stimuli)} 行) ← 判断中は見ない")
    print(f"       {out}/stimuli_blind.tsv   ({blind_n} 行) ← これを読み上げる")
    print(f"       {out}/stimuli_balance.tsv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
