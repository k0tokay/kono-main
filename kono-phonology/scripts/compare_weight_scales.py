#!/usr/bin/env python3
"""手起こしアクセント資料 (stimuli_blind.tsv) で重さスケールごとの F 位置予測を比較する.

    python3 scripts/compare_weight_scales.py out/stimuli/stimuli_blind.tsv

「音節化・長短」列は実現形（長音化・重子音化を含む）．綴りへ整列して基底形の
音節を復元し，基底形の重さで評価する（実現形を使うと「F の音節は長い」が自明になる）．
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from konophon import Word  # noqa: E402

VOWELS = set("aoeiyuv")


def align(spelled: str, realized: str):
    tags, p = [], 0
    for i, ch in enumerate(realized):
        if p < len(spelled) and ch == spelled[p]:
            tags.append(True); p += 1
        elif i > 0 and ch == realized[i - 1]:
            tags.append(False)
        else:
            raise ValueError(f"整列失敗: {spelled} / {realized} at {i}")
    if p != len(spelled):
        raise ValueError(f"整列失敗(残り): {spelled} / {realized}")
    # 子音の複写はコーダ側（前）を挿入扱いにする（オンセット保存）
    for i in range(1, len(realized)):
        if realized[i] == realized[i - 1] and realized[i] not in VOWELS and tags[i - 1] and not tags[i]:
            tags[i - 1], tags[i] = False, True
    return tags


def underlying_syllables(spelled: str, transcribed: str):
    realized = transcribed.replace(".", "")
    tags = align(spelled, realized)
    out, k, lng, gem = [], 0, set(), set()
    for j, syl in enumerate(transcribed.split(".")):
        u = ""
        for ch in syl:
            if tags[k]:
                u += ch
            else:
                (lng if ch in VOWELS else gem).add(j)
            k += 1
        out.append(u)
    return out, lng, gem


def weights(syl, scale: str) -> int:
    on, nu, co = len(syl.onset), len(syl.nucleus), len(syl.coda)
    w = 1 if nu == 1 else 2
    if scale == "rime":
        w += co
    elif scale == "onset":
        w += co + max(0, on - 1)
    elif scale == "katakana":
        w += (1 if co else 0) + max(0, on - 1)
    return w


SCALES = ["rime", "onset", "katakana"]
RULES = ["first_heavy", "heaviest", "last_heavy"]


def accent_index(acc: str):
    if "F" in acc:
        return acc.index("F"), "F"
    for i in range(len(acc) - 1):
        if acc[i] == "H" and acc[i + 1] == "L":
            return i, "HL"
    return None, "none"


def predict(ws, rule):
    heavy = [i for i, w in enumerate(ws) if w >= 2]
    if rule == "first_heavy":
        return heavy[0] if heavy else 0
    if rule == "heaviest":
        return ws.index(max(ws))
    if rule == "last_heavy":
        return heavy[-1] if heavy else len(ws) - 1


def main(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8"), delimiter="\t"))
    data = []
    for r in rows:
        w, tr, acc = r["単語"], r["音節化・長短"], r["高低"]
        try:
            syls, lng, gem = underlying_syllables(w, tr)
        except ValueError as e:
            print("skip:", e); continue
        if len(syls) != len(acc):
            print(f"skip: 音節数≠アクセント長 {w} {tr} {acc}"); continue
        data.append(dict(w=w, tr=tr, acc=acc, syls=Word(".".join(syls)).syllables, lng=lng, gem=gem,
                         mop=[s.spell for s in Word(w).syllables]))
    n = len(data)
    print(f"語数 {n}（重複含む）")

    by = defaultdict(list)
    for d in data:
        by[d["w"]].append((d["tr"], d["acc"]))
    dup = {k: v for k, v in by.items() if len(v) > 1}
    inc = {k: v for k, v in dup.items() if len(set(v)) > 1}
    print(f"重複語 {len(dup)}，うち転写かアクセントが不一致 {len(inc)}:")
    for k, v in inc.items():
        print("   ", k, v)

    mism = sorted({(d["w"], ".".join(s.spell for s in d["syls"]), ".".join(d["mop"])) for d in data
                   if [s.spell for s in d["syls"]] != d["mop"]})
    print(f"\n作者の音節境界が MOP と異なる語 {len(mism)}:")
    for m in mism:
        print("   ", m[0], "作者", m[1], "MOP", m[2])

    print("\nアクセント型:", dict(Counter(accent_index(d["acc"])[1] for d in data)))

    print("\n[E1] アクセント音節の基底重さが 2 以上である割合")
    for kind in ["F", "HL"]:
        sub = [d for d in data if accent_index(d["acc"])[1] == kind]
        print(f"  {kind} 型 {len(sub)} 語")
        for sc in SCALES:
            ok = sum(1 for d in sub if weights(d["syls"][accent_index(d['acc'])[0]], sc) >= 2)
            print(f"    {sc:9s} {ok}/{len(sub)} = {ok/len(sub):.2f}")

    print("\n[E2] アクセント位置の予測精度（規則×スケール）")
    for kind in ["F", "HL"]:
        sub = [d for d in data if accent_index(d["acc"])[1] == kind]
        pos = Counter(accent_index(d["acc"])[0] for d in sub)
        print(f"  {kind} 型 {len(sub)} 語  位置分布 {dict(sorted(pos.items()))}  多数派 {max(pos.values())/len(sub):.2f}")
        for rule in RULES:
            line = f"    {rule:12s}"
            for sc in SCALES:
                ok = sum(1 for d in sub
                         if predict([weights(s, sc) for s in d["syls"]], rule) == accent_index(d["acc"])[0])
                line += f"  {sc}={ok/len(sub):.2f}"
            print(line)

    print("\n[E2b] F 型で外れた語（first_heavy）")
    for sc in SCALES:
        bad = [(d["w"], d["tr"], d["acc"]) for d in data if accent_index(d["acc"])[1] == "F"
               and predict([weights(s, sc) for s in d["syls"]], "first_heavy") != accent_index(d["acc"])[0]]
        print(f"  {sc}: {len(bad)}")
        for b in bad:
            print("     ", *b)

    print("\n[E3] 長音化・重子音化の位置（アクセント音節からの相対位置）")
    rel_l, rel_g = Counter(), Counter()
    for d in data:
        ai, _ = accent_index(d["acc"])
        for j in d["lng"]:
            rel_l["none" if ai is None else j - ai] += 1
        for j in d["gem"]:
            rel_g["none" if ai is None else j - ai] += 1
    print("  長音化:", dict(sorted(rel_l.items(), key=str)))
    print("  重子音化:", dict(sorted(rel_g.items(), key=str)))
    for sc in SCALES:
        lf = [d for d in data if accent_index(d["acc"])[1] == "F" and weights(d["syls"][accent_index(d['acc'])[0]], sc) < 2]
        print(f"  {sc:9s}: 基底で軽い F 音節 {len(lf)} 語，うち長音化 {sum(1 for d in lf if accent_index(d['acc'])[0] in d['lng'])}")
    # 語末長音化
    fin = sum(1 for d in data if (len(d["syls"]) - 1) in d["lng"])
    print(f"  語末音節の長音化 {fin}/{n}")

    print("\n[E4] 語中 CC オンセット音節と直前音節")
    before, on_it = Counter(), Counter()
    for d in data:
        ai, _ = accent_index(d["acc"])
        for j, s in enumerate(d["syls"]):
            if len(s.onset) >= 2 and j > 0:
                before["長音化" if (j - 1) in d["lng"] else "長音化なし"] += 1
                before["アクセント" if ai == j - 1 else "非アクセント"] += 1
                on_it["長音化" if j in d["lng"] else "長音化なし"] += 1
                on_it["アクセント" if ai == j else "非アクセント"] += 1
    print("  直前音節:", dict(before))
    print("  CC 音節自身:", dict(on_it))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/stimuli/stimuli_blind.tsv")
