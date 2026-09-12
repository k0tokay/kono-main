# konophon — コノメノ音韻論の分析基盤

`phonology.tex` の記述を **実行可能な単一の定義** にし、その上に
音節化・パターン照合・統計・制約評価・刺激語生成を載せたもの．

```
konophon/
  data/phonology.toml   ← 唯一の定義元（音素・素性・IPA・結合表・韻律・制約）
  inventory.py          音素目録・素性・トークン化
  seq.py                音素列 Seq（不変列としての代数）
  syllable.py           音節と音節化（MOP、境界上書き、全解列挙）
  prosody.py            重さスケール（差し替え可能）・モーラ・アクセント
  word.py               音節化 + アクセント + 2種類の tier
  dsl.py                素性列 DSL（パターン・制約・書き換え規則）
  morphology.py         母音結合 + / 子音結合 ⊕
  phonetics.py          綴り → IPA
  constraints.py        制約の尤度評価（MaxEnt / O:E / ΔlogLik）
  stats.py              tier 抽象 + n-gram・遷移行列・エントロピー・PMI
  stimuli.py            統制された nonce 語の設計（手順 B）
  texgen.py             tex 表の生成
scripts/                コマンドライン
tests/                  tex の例を回帰テストにしたもの（42件）
```

## 必要なもの

Python 3.10 以上．コア（音素・音節化・DSL・刺激語生成）は標準ライブラリだけで動く．
統計と制約評価に `numpy` / `scipy` / `pandas` が要る．

```bash
pip install numpy scipy pandas
```

TOML は 3.11 以降なら標準の `tomllib`、3.10 以下では `tomli` があればそれ、
無ければ同梱の最小実装 `konophon/_minitoml.py` に自動で落ちる（追加インストール不要）．
最小実装は `tests/test_minitoml.py` で `tomllib` と完全一致することを検証している．

## 5分で試す

```bash
python3 -m pytest tests/ -q

D=../kono-dictionary-editor/src/data/konomeno-v5.json
A=../accent/data.tsv

python3 scripts/check_lexicon.py $A                  # 表と語彙の齟齬・輪郭調の2μ要件
python3 scripts/report_stats.py  $D --all            # どの tier に構造があるか
python3 scripts/eval_constraints.py $D --discover --top 20
python3 scripts/gen_stimuli.py --out-dir out/stimuli --lexicon $D --anchors 8
python3 scripts/gen_tex_tables.py -o generated/tables.tex
```

## ライブラリとして

```python
from konophon import Word, Seq, Corpus, Tiers, NgramModel, Baseline, evaluate

w = Word("paklata", accent="LFL")
w.syllabified                 # 'pa.kla.ta'
w.moras("rime")               # [1, 1, 1]
w.moras("onset_sensitive")    # [1, 2, 1]
w.contour_problems("rime")    # ['σ2 (kla) は F を担うが 1μ < 2μ']

w.count("[T][L]")                             # 破裂音+流音 の出現数
w.count("[weight=heavy]", "syllable")         # 重音節の数
w.count("[+cons, role=coda]")                 # コーダ子音の数

Seq.of("mes").vplus("ja")     # 母音結合（口蓋化まで適用）
```

## DSL の書き方

| 記法 | 意味 |
|---|---|
| `[+cons]` `[-son]` | 二値素性 |
| `[place=labial]` `[sonor>=6]` | カテゴリ／スカラー素性 |
| `[S] [Q] [T] [N] [L] [J]` / `C V S T ...` | 自然類（大文字1字は括弧なしで可） |
| `[]` | 任意のセグメント |
| `<ts>` / `ts` | 綴り字リテラル |
| `#` `.` | 語境界／音節境界 |
| `(A｜B)` `A?` `A*` `A+` `A{1,3}` | 選択・量化 |
| `*P` | P を禁止する markedness 制約 |
| `A -> B / C _ D` | 書き換え規則 |
| `[!N]` | 自然類の否定 |

音節境界は**明示的に `.` と書いたときだけ**意味を持つ透明な記号．
語境界 `#` は透明でない．だから `*[C][C][C][C]`（子音4連続の禁止）は
`suis.kant` のように境界をまたぐ場合もちゃんと数える．

セグメント tier では、各音素に所属音節の情報が注入される:
`role`(onset/nucleus/coda), `role_index`, `syl_index`, `from_end`,
`initial`, `final`, `penult`, `syl_weight`, `syl_mora`, `accent`.

音節 tier では: `onset_size`, `nucleus_size`, `coda_size`, `open`,
`shape`, `mora`, `weight`, `accent`, `initial`, `final`, `penult`, `from_end`.

## 制約評価の読み方

```bash
python3 scripts/eval_constraints.py $D '*[N][N]' '*[Q][C]' --fit
```

| 列 | 意味 |
|---|---|
| `O` | 語彙中の実観測違反数 |
| `E` | baseline（音素頻度だけを保ったランダム語）下の期待違反数 |
| `O/E` | 1 より十分小さければ「避けられている」 |
| `p` | 違反を含む語の割合についての二項検定 |
| `dLL` | その制約を文法に足したときの対数尤度の改善．**候補間の比較はこれ** |

baseline は `--baseline cv|unigram|positional` で選ぶ．
`cv` は CV 骨格の分布を保つので「骨格を説明変数から外して、どの子音が
どこに来るかだけを見る」用．骨格そのものの制約（母音3連続の禁止など）を
検出したいときは `unigram` にすること（`cv` だと期待値が構造的に 0 になる）．

## 刺激語生成（手順 B）

```bash
python3 scripts/gen_stimuli.py --out-dir out/stimuli --lexicon $D --anchors 8 --seed 42
```

3つのファイルが出る:

- `stimuli_key.tsv` — 設計行列。**判断中は開かないこと**
- `stimuli_blind.tsv` — 読み上げ用。シャッフル済み・設計情報なし・反復項目入り。
  列名は `accent/data.tsv` と揃えてあるのでそのまま追記できる
- `stimuli_balance.tsv` — 因子水準ごとの件数

生成時に **MOP で意図と違う構造に再解析される語は自動的に落とす**
（読み手が別の構造の語を読んでしまうため）。落とした設計は標準出力に
理由つきで出るので、黙って被覆が減ることはない。

録音の順番が重要:

1. **仮説を議論する前に** `stimuli_blind.tsv` の順で通しで読み上げて録音する
2. 読みながら「高低」だけ埋める（音節化は後で音声から決める）
3. 反復項目の一致率＝自分の判断の再現率
4. その後で f0 と母音長を測る（手順 C）

## 設計の詳細

`DESIGN.md` を参照．とくに「重さスケールを差し替え可能にした理由」と
「制約評価が何を帰無仮説にしているか」はそこに書いてある．
