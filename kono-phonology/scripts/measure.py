#!/usr/bin/env python3
"""キャリア文で読み上げた録音から音節ごとの f0・持続時間を測る（手順 C）.

    python3 scripts/measure.py recordings/2026-08-15_001.m4a \\
        --stimuli out/stimuli/stimuli_blind.tsv --out out/measure

出力:

``measurements.tsv``
    音節1行の測定表（f0 の開始・終端・傾き・レンジ、持続時間、自動ラベル）
``tokens.tsv``
    語1行の要約（目標語区間・キャリア照合スコア・自動アクセント列・警告）
``alignment.txt``
    発話と刺激の対応、統合／未使用の一覧
``<録音名>.TextGrid``
    Praat で開いて境界を手修正するためのもの（utterance / target / syllable 層）

自動ラベル（``auto``）は目安であって判定ではない．しきい値次第で変わるので、
分析には ``level_st``（語内での相対的な高さ）と ``excursion_st``
（音節内での f0 変化量）の生値を使うこと．
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from konophon import Word, inventory  # noqa: E402
from konophon.acoustics import Recording, analyse, write_textgrid  # noqa: E402

AUDIO_NEEDS_CONVERT = {".m4a", ".mp3", ".aac", ".ogg", ".opus", ".caf", ".flac"}


def to_wav(path: Path) -> Path:
    if path.suffix.lower() not in AUDIO_NEEDS_CONVERT:
        return path
    out = Path(tempfile.gettempdir()) / (path.stem + ".wav")
    if not out.exists():
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", str(out)],
            check=True,
        )
    return out


def load_stimuli(path: Path, inv) -> list[Word]:
    rows = list(csv.DictReader(path.open(encoding="utf-8"), delimiter="\t"))
    words = []
    for r in rows:
        spell = (r.get("単語") or "").strip()
        if not spell:
            continue
        words.append(Word(spell, inv=inv, gloss=(r.get("翻訳") or "").strip(),
                          meta={"id": r.get("id", ""), "order": r.get("順", "")}))
    return words


def write_tsv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", type=Path)
    ap.add_argument("--stimuli", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/measure"))
    ap.add_argument("--carrier", default="suffix", choices=["suffix", "frame"],
                    help="suffix: X kino danktai / frame: kino X danktai")
    ap.add_argument("--threshold-frac", type=float, default=0.40)
    ap.add_argument("--min-silence", type=float, default=0.35)
    a = ap.parse_args(argv)

    inv = inventory()
    words = load_stimuli(a.stimuli, inv)
    print(f"[刺激] {len(words)} 語")

    wav = to_wav(a.audio)
    rec = Recording.load(wav)
    print(f"[録音] {a.audio.name}  {rec.duration:.1f}s")

    results, align, carrier = analyse(
        rec,
        words,
        carrier_mode=a.carrier,
        threshold_frac=a.threshold_frac,
        min_silence=a.min_silence,
        progress=lambda i, n: print(f"   ... {i}/{n}", flush=True),
    )
    print()
    print(align.report())

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "alignment.txt").write_text(align.report() + "\n", encoding="utf-8")

    mrows, trows = [], []
    for r in results:
        auto = "".join(m.auto_label for m in r.syllables)
        trows.append({
            "order": r.stimulus_index + 1,
            "id": r.word.meta.get("id", ""),
            "単語": r.word.spell,
            "音節化": r.word.syllabified,
            "n_syl": r.word.n_syllables,
            "auto_accent": auto,
            "target_start": round(r.target[0], 3),
            "target_end": round(r.target[1], 3),
            "target_dur_ms": round((r.target[1] - r.target[0]) * 1000, 1),
            "carrier_score": round(r.carrier_score, 3),
            "warnings": "; ".join(r.warnings),
        })
        for m in r.syllables:
            mrows.append({
                "order": r.stimulus_index + 1,
                "単語": r.word.spell,
                "n_syl": r.word.n_syllables,
                "from_end": r.word.n_syllables - m.index,
                **m.as_row(),
            })
    write_tsv(a.out / "measurements.tsv", mrows)
    write_tsv(a.out / "tokens.tsv", trows)

    tiers = {
        "utterance": [(r.utterance[0], r.utterance[1], r.word.spell) for r in results],
        "target": [(r.target[0], r.target[1], r.word.spell) for r in results],
        "syllable": [(m.start, m.end, m.label) for r in results for m in r.syllables],
    }
    tg = a.out / (Path(a.audio).stem + ".TextGrid")
    write_textgrid(tg, rec.duration, tiers)

    warn = [t for t in trows if t["warnings"]]
    print(f"\n[出力] {a.out}/measurements.tsv  ({len(mrows)} 音節)")
    print(f"       {a.out}/tokens.tsv         ({len(trows)} 語)")
    print(f"       {tg.name}                  ← Praat で境界を手修正できる")
    print(f"\n[警告つきの語] {len(warn)} / {len(trows)}")
    for t in warn[:15]:
        print(f"   #{t['order']:3d} {t['単語']:12s} {t['warnings']}")
    if len(warn) > 15:
        print(f"   ... 他 {len(warn) - 15} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
