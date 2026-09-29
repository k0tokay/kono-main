"""造語候補の機械検査（造語章「手順（意味先行）」の検査段）．

  python3 scripts/check_candidates.py tselk feesk ...        # 引数で
  printf 'tselk\\nfeesk\\n' | python3 scripts/check_candidates.py   # 標準入力で
  python3 scripts/check_candidates.py --parent 1092 byylek   # 親の下での語頭2字の共有も見る

報告する項目：
  音素化・結合表での厳密な音節化・子音4連続（不可なら ✗）
  F型の既定位置（音韻章の定義）と，そこでの長音化の要否（長核か共鳴子音コーダでなければ要）
  語彙の全存命項目との綴りの Levenshtein 距離 ≤1（あれば △，造語章では差し替え）
  3文字以上の「音列」項目との重なり，語頭2字の共有数（全体・親の下）
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from konophon import Word  # noqa: E402
from konophon.syllable import Syllabifier  # noqa: E402

DICT = ROOT.parent / "kono-dictionary-editor" / "src" / "data" / "konomeno-v5.json"
SONORANT_MANNERS = {"nasal", "liquid", "approximant"}


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def f_position(word):
    """音韻章「F型の既定位置」：単音節ならそこ，多音節なら語末を除く最初の重音節，なければ後ろから2番目．"""
    weights = word.weights("onset_sensitive")
    if len(weights) == 1:
        return 0
    for i, w in enumerate(weights[:-1]):
        if w != "light":
            return i
    return len(weights) - 2


def needs_lengthening(syllable):
    if len(syllable.nucleus) >= 2:
        return False
    coda = list(syllable.coda)
    return not (coda and coda[0].features.get("manner") in SONORANT_MANNERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("forms", nargs="*")
    ap.add_argument("--parent", type=int, help="この親の下の語と語頭2字の共有を見る")
    args = ap.parse_args()
    forms = args.forms or [line.strip() for line in sys.stdin if line.strip()]

    words = [w for w in json.load(open(DICT))["words"] if w]
    lexicon = [w["entry"] for w in words if w["category"] == "語彙" and not w["entry"].startswith("〈")]
    sequences = [w["entry"] for w in words if w["category"] == "音列" and len(w["entry"]) >= 3]
    by_id = {w["id"]: w for w in words}
    siblings = []
    if args.parent is not None:
        siblings = [by_id[c]["entry"] for c in by_id[args.parent]["lower_covers"] if c in by_id]
    strict = Syllabifier(fallback_relaxed=False)

    for form in forms:
        try:
            word = Word(form)
        except Exception as error:  # noqa: BLE001
            print(f"{form:14s} ✗ 音素化・音節化できない（{error}）")
            continue
        problems = []
        if not strict.all_parses(word.seq):
            problems.append(f"結合表で音節化できない（緩和: {word.syllabified}）")
        run = longest = 0
        for seg in word.segments:
            run = run + 1 if not seg.features.get("syl") else 0
            longest = max(longest, run)
        if longest >= 4:
            problems.append("子音4連続")
        hard = bool(problems)
        k = f_position(word)
        f_syl = word.syllables[k]
        f_note = f"F=σ{k + 1} {f_syl.spell}" + ("（長音化が要る）" if needs_lengthening(f_syl) else "")
        near = sorted({e for e in lexicon if e != form and lev(form, e) <= 1})
        if near:
            problems.append("距離≤1: " + ",".join(near))
        overlaps = sorted({s for s in sequences if s in form})
        head = sum(1 for e in lexicon if e[:2] == form[:2])
        sib = [e for e in siblings if e[:2] == form[:2]]
        tag = "✗" if hard else ("△" if near else "✓")
        extra = f"語頭2字 全体{head}" + (f"・兄弟{len(sib)}({','.join(sib)})" if args.parent is not None else "")
        if overlaps:
            extra += f"／音列 {','.join(overlaps)}"
        print(f"{form:14s} {tag} {word.syllabified:14s} {f_note}  {'；'.join(problems) or '問題なし'}  （{extra}）")


if __name__ == "__main__":
    main()
