# 分布矯正（試作）

コノメノの音素分布が上位10音素に偏りすぎている（82.5%）問題への対処．
gogaku.tex「音素の分布」の方針（環境条件付き音韻変化の一斉適用）を実行可能にしたもの．

## 構成

| ファイル | 役割 |
|---|---|
| `rules.toml` | 書き換え規則（DSL）．`enabled=false` で個別に切れる |
| `../konophon/rewrite.py` | 規則を語へ適用する（`Word.segment_tier` 上で照合，`#`・音節位置・role が使える） |
| `../scripts/correct_distribution.py` | 辞書全体に適用し，変更語・衝突・前後の指標を `out/correction/` に出す |
| `../typology/compare_dist.py` | ランク分布（音素・音節型・音節・bigram・クラスタ・語長）を参照言語と比較 |
| `../typology/ipa_classes.py` | NorthEuraLex の IPA を粗い素性（C/V・調音法・有声）へ落とす |
| `../typology/raw/northeuralex-forms.csv` | 参照データ（lexibank/northeuralex CLDF, 約1000概念×107言語, IPA つき） |

## 手順

```bash
python3 scripts/correct_distribution.py ../kono-dictionary-editor/src/data/konomeno-v5.json
python3 typology/compare_dist.py --langs rus khk --extra "Konomeno-after=out/correction/after.ipa.txt" \
    --out typology/output/compare_after.md
```

## 指標の選び方（文献）

- Tambovtsev & Martindale (2007): 音素頻度は Yule 分布．gogaku.tex が引くもの．
- Macklin-Cordes & Round (2020, *Frontiers in Psychology*, "Re-evaluating Phoneme Frequencies"):
  R² と対数対数回帰は信頼できない．目録全体には指数（幾何）分布がよく合い，
  上位だけがべき則的．MLE と尤度比検定を使うべき．→ 本スクリプトは H/log2(n)，上位k占有率，
  幾何分布の MLE，幾何 vs Yule の対数尤度を出す．
- arXiv:2603.02860 (2026): 音素分布は対称 Dirichlet(α) の順序統計量で近似でき α ≈ 19.47·n^-0.95．
  相対エントロピーは目録 11 音素で 0.91，160 音素で 0.71．→ `dirichlet_expected` で期待曲線を描く．
- 音節型: ULSID（Maddieson 1992; Rousset 2004）で CV が約 54%，次いで CVC．複雑な型ほど稀．
  音節・bigram・語長などの単位についてランク分布の形を主張する論文は見つからなかった
  （Wan et al. 2024 PACLIC は台湾華語の音節型 12 種で Yule の方が Zipf より合うと報告）．
  そのため単位ごとに同じ指標を出して参照言語と直接比べる方式にした．
