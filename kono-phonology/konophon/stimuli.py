"""刺激語（nonce word）の設計と生成 — 手順 B.

# なぜこれが要るか

現在のアクセント資料は実語彙が中心で、複合語・意味・頻度が交絡している．
統制された nonce 語がないと、どの仮説も関連データ点が 2〜3 個しか持てず
反証不能になる（``pakata`` vs ``paklata`` の対立が 1 組しか無い、など）．

# 設計

**中核となる完全交差 + 1因子ずつの拡張ブロック**という構成にしてある．
完全交差だけだと組み合わせ爆発し、1因子ずつだけだと交互作用が見えない．

対象音節（TARGET）以外はすべて軽い CV フィラー（母音は ``a`` 固定、
子音は決定的に回転させて特定の子音との交絡を避ける）にする．

因子:

``onset``     ∅ / C / CC（さらに CC はソノリティ勾配で TL, SL, ST, SN, TJ, NL に分ける）
``nucleus``   V / VV(長) / VV(二重母音)
``coda``      ∅ / N / T / S / NC / SC
``position``  対象音節の位置（語頭・語中・語末）
``length``    2〜4 音節

CC のソノリティ内訳を分けてあるのが要点で、「複雑オンセット一般が効く」
のか「ソノリティ勾配が効く」のかを区別できる．

# 検証

生成後に必ず次を確認し、通らないものは落とす（落とした理由は集計して
報告する。黙って切り捨てない）:

1. 綴りが音素列に分解できる
2. **MOP による音節化が意図した構造と一致する**（一致しないと、読み手は
   別の構造の語を読んでしまう）
3. hard 制約に違反しない
4. 既存語彙と同形でない（意味の干渉を避ける）
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .constraints import Grammar
from .inventory import Inventory, inventory as default_inventory
from .syllable import SyllabifyError
from .word import Word

# ---------------------------------------------------------------------------
# 因子の水準
# ---------------------------------------------------------------------------

#: オンセット: 水準名 -> 候補（複数あるものは決定的に回転させて使う）
ONSETS: dict[str, tuple[str, ...]] = {
    "none": ("",),
    "C.T": ("p", "t", "k"),
    "C.S": ("f", "s"),
    "C.N": ("m", "n"),
    "C.L": ("l",),
    "CC.TL": ("kl", "pl", "bl", "gl"),   # 破裂音 + 流音（ソノリティ差 大）
    "CC.SL": ("fl", "sl", "zl"),         # 摩擦音 + 流音
    "CC.ST": ("sk", "st", "sp"),         # 摩擦音 + 破裂音（ソノリティ差 逆）
    "CC.SN": ("sn", "fn", "sm"),         # 摩擦音 + 鼻音
    "CC.TJ": ("kw", "tw", "pj"),         # 破裂音 + 接近音（ソノリティ差 最大）
    "CC.NL": ("nl", "ml"),               # 鼻音 + 流音（ソノリティ差 小）
}

#: 核
NUCLEI: dict[str, tuple[str, ...]] = {
    "V": ("a", "o", "e"),
    "VV.long": ("aa", "oo", "ee"),
    "VV.diph": ("ai", "oi", "au"),
}

#: コーダ
CODAS: dict[str, tuple[str, ...]] = {
    "none": ("",),
    "N": ("n", "m"),
    "T": ("k", "t", "p"),
    "S": ("s", "f"),
    "NC": ("nt", "nk"),
    "SC": ("sk", "st"),
}

#: フィラー音節の子音（決定的に回転させる）．
#: 摩擦音を含めてあるのは、対象音節のコーダが後続音節のオンセットに
#: 吸い上げられる（``pas.ta.ta`` → ``pa.sta.ta``）のを避けるため．
#: S は T/N/L/J を従えられるので、コーダ直後のフィラーは摩擦音・破擦音に
#: しないと MOP に負ける．
FILLER_ONSETS = ("p", "t", "k", "n", "m", "l", "s", "f", "c")
FILLER_VOWEL = "a"

BASELINE = {"onset": "C.T", "nucleus": "V", "coda": "none"}


# ---------------------------------------------------------------------------
# 設計オブジェクト
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stimulus:
    """1つの刺激語."""

    spell: str
    syllabified: str
    block: str
    factors: dict[str, str]
    target_index: int
    n_syllables: int

    @property
    def item_id(self) -> str:
        """設計を推測できない ID（key ファイルとの突き合わせ用）."""
        return hashlib.sha1(self.spell.encode()).hexdigest()[:8]

    def as_key_row(self) -> dict:
        return {
            "id": self.item_id,
            "単語": self.spell,
            "意図した音節化": self.syllabified,
            "block": self.block,
            "target": self.target_index + 1,
            "n_syl": self.n_syllables,
            **{f"f_{k}": v for k, v in self.factors.items()},
        }

    def as_blind_row(self) -> dict:
        """判断用．設計情報は一切入れない（data.tsv と同じ列名）."""
        return {
            "id": self.item_id,
            "単語": self.spell,
            "翻訳": "--",
            "音節化・長短": "",
            "高低": "",
            "確信度": "",
            "メモ": "",
        }


@dataclass
class GenerationReport:
    kept: int = 0
    dropped_resyllabified: list[tuple[str, str, str]] = field(default_factory=list)
    dropped_illegal: list[tuple[str, str]] = field(default_factory=list)
    dropped_lexical: list[str] = field(default_factory=list)
    dropped_duplicate: int = 0

    def summary(self) -> str:
        return (
            f"採用 {self.kept} 語 / "
            f"再音節化で除外 {len(self.dropped_resyllabified)} / "
            f"制約違反で除外 {len(self.dropped_illegal)} / "
            f"既存語と衝突 {len(self.dropped_lexical)} / "
            f"重複 {self.dropped_duplicate}"
        )


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------


def _pick(options: Sequence[str], counter: int) -> str:
    return options[counter % len(options)]


def _filler_onset(rot: int, avoid: str, prev_coda: str, inv: Inventory) -> str:
    """フィラー音節のオンセットを選ぶ.

    ``prev_coda`` の末尾子音と合わせて合法なオンセット対になる子音は
    避ける（MOP に吸い上げられて意図した構造が壊れるため）．
    """
    prev = inv.tokenize(prev_coda)[-1].spell if prev_coda else ""
    cands = [
        c
        for c in FILLER_ONSETS
        if c != avoid and (not prev or (prev, c) not in inv.legal_onset_pairs)
    ]
    if not cands:
        cands = [c for c in FILLER_ONSETS if c != avoid] or list(FILLER_ONSETS)
    return cands[rot % len(cands)]


def _build_spell(
    n_syl: int, target: int, onset: str, nucleus: str, coda: str, rot: int, inv: Inventory
) -> tuple[str, str]:
    """(綴り, 意図した音節化) を作る."""
    syls: list[str] = []
    fill = 0
    prev_coda = ""
    for i in range(n_syl):
        if i == target:
            syls.append(onset + nucleus + coda)
            prev_coda = coda
        else:
            c = _filler_onset(rot + fill, onset[:1], prev_coda, inv)
            syls.append(c + FILLER_VOWEL)
            prev_coda = ""
            fill += 1
    return "".join(syls), ".".join(syls)


def _make(
    block: str,
    factors: dict[str, str],
    n_syl: int,
    target: int,
    rot: int,
    inv: Inventory,
) -> tuple[Stimulus | None, str, str]:
    """1件生成し、(刺激 or None, 失敗理由, 実際の音節化) を返す."""
    onset = _pick(ONSETS[factors["onset"]], rot)
    nucleus = _pick(NUCLEI[factors["nucleus"]], rot)
    coda = _pick(CODAS[factors["coda"]], rot)
    if target != 0 and onset == "":
        return None, "語頭以外で ∅ オンセットは作らない", ""
    spell, intended = _build_spell(n_syl, target, onset, nucleus, coda, rot, inv)
    try:
        w = Word(spell, inv=inv)
    except (SyllabifyError, ValueError, KeyError) as e:
        return None, f"音節化不能: {e}", ""
    if w.syllabified != intended:
        return None, "resyllabified", w.syllabified
    if w.notes:
        return None, "; ".join(w.notes), w.syllabified
    return (
        Stimulus(spell, intended, block, dict(factors), target, n_syl),
        "",
        w.syllabified,
    )


def generate(
    blocks: Iterable[str] = ("core", "onset", "coda", "nucleus", "position", "length"),
    *,
    inv: Inventory | None = None,
    lexicon: Iterable[str] = (),
    grammar: Grammar | None = None,
) -> tuple[list[Stimulus], GenerationReport]:
    """ブロックを指定して刺激語を生成する."""
    inv = inv or default_inventory()
    grammar = grammar or Grammar.from_inventory(inv)
    lex = {s for s in lexicon}
    report = GenerationReport()
    seen: set[str] = set()
    out: list[Stimulus] = []
    rot = 0

    def emit(block: str, factors: dict[str, str], n_syl: int, target: int):
        nonlocal rot
        for attempt in range(6):  # 回転をずらして数回試す
            st, why, actual = _make(block, factors, n_syl, target, rot + attempt, inv)
            if st is None:
                if why == "resyllabified":
                    report.dropped_resyllabified.append(
                        (f"{block}:{factors}", "→".join([str(n_syl), str(target)]), actual)
                    )
                elif why.startswith("語頭以外"):
                    return
                else:
                    report.dropped_illegal.append((f"{block}:{factors}", why))
                continue
            if st.spell in lex:
                report.dropped_lexical.append(st.spell)
                continue
            if st.spell in seen:
                report.dropped_duplicate += 1
                continue
            w = Word(st.spell, inv=inv)
            if not grammar.is_legal(w):
                report.dropped_illegal.append((st.spell, "hard 制約違反"))
                continue
            seen.add(st.spell)
            out.append(st)
            report.kept += 1
            rot += 1
            return
        rot += 1

    blocks = set(blocks)

    # --- core: onset × nucleus × coda × position の縮約完全交差 --------------
    if "core" in blocks:
        for onset in ("C.T", "CC.TL"):
            for nucleus in ("V", "VV.long"):
                for coda in ("none", "N", "T"):
                    for target in (0, 1, 2):
                        emit(
                            "core",
                            {"onset": onset, "nucleus": nucleus, "coda": coda},
                            3,
                            target,
                        )

    # --- onset: オンセット型を全水準（他は baseline，位置は 3 通り） -----------
    if "onset" in blocks:
        for onset in ONSETS:
            for coda in ("none", "N"):
                for target in (0, 1, 2):
                    emit("onset", {**BASELINE, "onset": onset, "coda": coda}, 3, target)

    # --- coda: コーダ型を全水準 ---------------------------------------------
    if "coda" in blocks:
        for coda in CODAS:
            for onset in ("C.T", "CC.TL"):
                for target in (0, 1, 2):
                    emit("coda", {**BASELINE, "onset": onset, "coda": coda}, 3, target)

    # --- nucleus: 核の型を全水準 --------------------------------------------
    if "nucleus" in blocks:
        for nucleus in NUCLEI:
            for coda in ("none", "N"):
                for target in (0, 1, 2):
                    emit("nucleus", {**BASELINE, "nucleus": nucleus, "coda": coda}, 3, target)

    # --- position: 重い音節を 1 つだけ置き、位置だけ動かす ---------------------
    if "position" in blocks:
        for heavy in ({"coda": "N"}, {"nucleus": "VV.long"}, {"onset": "CC.TL"}):
            for n_syl in (2, 3, 4):
                for target in range(n_syl):
                    emit("position", {**BASELINE, **heavy}, n_syl, target)

    # --- length: すべて軽い CV の語（アクセントの既定値を見る） ----------------
    if "length" in blocks:
        for n_syl in (2, 3, 4, 5):
            for _ in range(2):
                emit("length", dict(BASELINE), n_syl, 0)

    return out, report


# ---------------------------------------------------------------------------
# ブラインド化
# ---------------------------------------------------------------------------


def blind_order(
    stimuli: Sequence[Stimulus],
    *,
    seed: int = 0,
    repeat_rate: float = 0.10,
    anchors: Sequence[str] = (),
    min_repeat_gap: int = 20,
) -> list[dict]:
    """判断用の並びを作る.

    - 設計順を完全にシャッフルする（パラダイム構造が見えると内省が
      規則に引っ張られる．``accent/memo.md`` にある通り、これは実在の危険）
    - ``repeat_rate`` の割合の項目を 2 回入れる（判断の再現率＝実質的な
      信頼区間の推定になる）．反復は ``min_repeat_gap`` 以上離す
    - ``anchors`` に実語彙を渡すと錨として混ぜる（既知の語で調子を確認できる）
    """
    import random

    rng = random.Random(seed)
    rows = [s.as_blind_row() for s in stimuli]
    for a in anchors:
        rows.append({"id": hashlib.sha1(a.encode()).hexdigest()[:8], "単語": a,
                     "翻訳": "(既知語)", "音節化・長短": "", "高低": "", "確信度": "", "メモ": ""})
    rng.shuffle(rows)

    n_rep = int(len(stimuli) * repeat_rate)
    repeats = rng.sample(rows, min(n_rep, len(rows)))
    out = list(rows)
    for r in repeats:
        base = out.index(r)
        lo = min(len(out), base + min_repeat_gap)
        pos = rng.randint(lo, len(out)) if lo < len(out) else len(out)
        out.insert(pos, {**r, "メモ": ""})
    for i, r in enumerate(out, 1):
        r["順"] = i
    cols = ["順", "id", "単語", "翻訳", "音節化・長短", "高低", "確信度", "メモ"]
    return [{c: r.get(c, "") for c in cols} for r in out]


def balance_report(stimuli: Sequence[Stimulus]):
    """因子水準ごとの件数（設計のバランス確認）."""
    import pandas as pd

    rows = []
    for s in stimuli:
        for k, v in s.factors.items():
            rows.append({"factor": k, "level": v, "block": s.block, "target": s.target_index + 1})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return (
        df.value_counts(["factor", "level"])
        .reset_index(name="n")
        .sort_values(["factor", "level"], ignore_index=True)
    )
