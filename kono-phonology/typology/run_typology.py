"""
音韻類型分析メインスクリプト
エストニア語・クロアチア語 vs コノメノ・サイメノの比較

使い方:
  python3 run_typology.py
  python3 run_typology.py --lang est-Latn wordlists/estonian.txt  # 単一言語
"""

import json
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Hiragino Sans"

import epitran

from analysis import PhonemeStats, BOS, EOS
from kono_ipa import spelling_to_ipa

BASE = Path(__file__).resolve().parent
KONO_BASE = BASE.parent.parent


# --- データローダー ---

def load_epitran_words(wordlist_path, lang_code):
    epi = epitran.Epitran(lang_code)
    words_ph = []
    seen = set()
    with open(wordlist_path) as f:
        for line in f:
            w = line.strip()
            if not w or w in seen:
                continue
            seen.add(w)
            if not re.fullmatch(r"[a-zA-ZäöüõšžčćđÄÖÜÕŠŽČĆĐéèêëàáâãåæçñ]+", w):
                continue
            ph_list = epi.trans_list(w)
            if ph_list:
                words_ph.append(ph_list)
    return words_ph


def load_kono_words(dict_path):
    sys.path.insert(0, str(BASE.parent))
    from phonemes import tokenize
    with open(dict_path) as f:
        data = json.load(f)
    words_ph = []
    for entry in data["words"]:
        if not entry:
            continue
        form = entry["entry"]["form"]
        if not re.fullmatch(r"[a-z]+", form):
            continue
        ph = tokenize(form)
        if ph:
            words_ph.append(spelling_to_ipa(ph))
    return words_ph


# --- 可視化 ---

def plot_frequency_comparison(stats_list, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]

    ax = axes[0]
    for i, st in enumerate(stats_list):
        ranks, freqs = st.ranked_freq()
        ax.scatter(ranks, freqs, s=15, color=colors[i], alpha=0.7, label=f"{st.name} (n={st.n_types})")
        ax.plot(ranks, freqs, color=colors[i], alpha=0.3, linewidth=1)
    ax.set_xlabel("Rank")
    ax.set_ylabel("相対頻度")
    ax.set_title("音素頻度分布 (rank-frequency)")
    ax.legend(fontsize=9)

    ax = axes[1]
    for i, st in enumerate(stats_list):
        ranks, freqs = st.ranked_freq()
        ax.scatter(np.log(ranks), np.log(freqs), s=15, color=colors[i], alpha=0.7, label=st.name)
        ax.plot(np.log(ranks), np.log(freqs), color=colors[i], alpha=0.3, linewidth=1)
    ax.set_xlabel("Log Rank")
    ax.set_ylabel("Log Frequency")
    ax.set_title("Log-log プロット")
    ax.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(output_dir / "freq_comparison.png", dpi=150)
    plt.close()


def plot_entropy_comparison(stats_list, output_dir):
    names = [st.name for st in stats_list]
    summaries = [st.summary_dict() for st in stats_list]
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # ユニグラムエントロピー vs 最大エントロピー
    ax = axes[0]
    h_uni = [s["H_unigram"] for s in summaries]
    h_max = [s["H_max"] for s in summaries]
    x = np.arange(len(names))
    ax.bar(x - 0.2, h_uni, 0.35, label="H(X)", color=colors[:len(names)])
    ax.bar(x + 0.2, h_max, 0.35, label="H_max = log2(n)", color="lightgray")
    for i, (hu, hm) in enumerate(zip(h_uni, h_max)):
        ax.text(i - 0.2, hu + 0.05, f"{hu:.2f}", ha="center", fontsize=8)
        ax.text(i + 0.2, hm + 0.05, f"{hm:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("bits")
    ax.set_title("ユニグラムエントロピー H(X)")
    ax.legend(fontsize=8)

    # 条件付きエントロピー
    ax = axes[1]
    h_cond = [s["H_cond"] for s in summaries]
    bars = ax.bar(x, h_cond, color=colors[:len(names)])
    for i, v in enumerate(h_cond):
        ax.text(i, v + 0.05, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("bits")
    ax.set_title("条件付きエントロピー H(X_t | X_{t-1})")

    # 相互情報量
    ax = axes[2]
    mi = [s["MI"] for s in summaries]
    bars = ax.bar(x, mi, color=colors[:len(names)])
    for i, v in enumerate(mi):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("bits")
    ax.set_title("相互情報量 I(X_{t-1}; X_t)")

    plt.tight_layout()
    plt.savefig(output_dir / "entropy_comparison.png", dpi=150)
    plt.close()


def plot_transition_heatmap(st, output_dir):
    symbols, P = st.transition_prob()
    inner = [s for s in symbols if s not in (BOS, EOS)]
    top = [s for s, _ in st.unigram.most_common(20)]
    show = [BOS] + top + [EOS]
    idx_map = {s: i for i, s in enumerate(symbols)}
    show_idx = [idx_map[s] for s in show if s in idx_map]
    show_labels = [s for s in show if s in idx_map]

    sub = P[np.ix_(show_idx, show_idx)]

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(sub, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(show_labels)))
    ax.set_xticklabels(show_labels, fontsize=7, rotation=45)
    ax.set_yticks(range(len(show_labels)))
    ax.set_yticklabels(show_labels, fontsize=7)
    ax.set_xlabel("x_t (次)")
    ax.set_ylabel("x_{t-1} (前)")
    ax.set_title(f"{st.name} — 遷移確率 P(x_t | x_{{t-1}})")
    plt.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout()
    plt.savefig(output_dir / f"transition_{st.name}.png", dpi=150)
    plt.close()


def plot_pmi_heatmap(st, output_dir):
    symbols, pmi = st.pmi_matrix(min_count=2)
    top = [s for s, _ in st.unigram.most_common(20)]
    show = [BOS] + top + [EOS]
    idx_map = {s: i for i, s in enumerate(symbols)}
    show_idx = [idx_map[s] for s in show if s in idx_map]
    show_labels = [s for s in show if s in idx_map]

    sub = pmi[np.ix_(show_idx, show_idx)]
    masked = np.where(np.isnan(sub), 0, sub)

    fig, ax = plt.subplots(figsize=(10, 8))
    vmax = np.nanmax(np.abs(sub[~np.isnan(sub)])) if np.any(~np.isnan(sub)) else 1
    im = ax.imshow(masked, cmap="RdBu_r", aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(show_labels)))
    ax.set_xticklabels(show_labels, fontsize=7, rotation=45)
    ax.set_yticks(range(len(show_labels)))
    ax.set_yticklabels(show_labels, fontsize=7)
    ax.set_xlabel("x_t (次)")
    ax.set_ylabel("x_{t-1} (前)")
    ax.set_title(f"{st.name} — PMI(x_{{t-1}}, x_t)")
    plt.colorbar(im, ax=ax, fraction=0.046)
    plt.tight_layout()
    plt.savefig(output_dir / f"pmi_{st.name}.png", dpi=150)
    plt.close()


def print_report(st):
    s = st.summary_dict()
    print(f"\n{'='*60}")
    print(f"  {s['name']}")
    print(f"{'='*60}")
    print(f"  語数: {s['n_words']}")
    print(f"  音素トークン数: {s['n_tokens']}")
    print(f"  音素種類数: {s['n_phonemes']}")
    print(f"  H(X) ユニグラムエントロピー: {s['H_unigram']:.3f} bits  (H_max = {s['H_max']:.3f})")
    print(f"  H(X_t|X_{{t-1}}) 条件付きエントロピー: {s['H_cond']:.3f} bits")
    print(f"  I(X_{{t-1}};X_t) 相互情報量: {s['MI']:.3f} bits")
    print()

    print("  音素頻度 (上位20):")
    for i, (ph, cnt) in enumerate(st.unigram.most_common(20), 1):
        pct = cnt / st.n_tokens * 100
        bar = "#" * int(pct * 2)
        print(f"    {i:2d}. {ph:4s} {cnt:5d}  ({pct:5.2f}%)  {bar}")
    print()

    print("  語頭音素 (上位10):")
    total_init = sum(st.initial.values())
    for ph, cnt in st.initial.most_common(10):
        print(f"    {ph:4s} {cnt:4d}  ({cnt/total_init*100:5.2f}%)")
    print()

    print("  語末音素 (上位10):")
    total_fin = sum(st.final.values())
    for ph, cnt in st.final.most_common(10):
        print(f"    {ph:4s} {cnt:4d}  ({cnt/total_fin*100:5.2f}%)")
    print()

    print("  PMI上位15 (好まれる連接):")
    for a, b, pmi_val, cnt in st.top_pmi_pairs(min_count=2, top_n=15):
        print(f"    {a:5s} → {b:5s}  PMI={pmi_val:+.2f}  (n={cnt})")
    print()

    print("  PMI下位15 (避けられる連接):")
    for a, b, pmi_val, cnt in st.bottom_pmi_pairs(min_count=2, top_n=15):
        print(f"    {a:5s} → {b:5s}  PMI={pmi_val:+.2f}  (n={cnt})")


def main():
    output_dir = BASE / "output"
    output_dir.mkdir(exist_ok=True)

    print("音韻類型分析")
    print("=" * 60)

    # --- データ読み込み ---
    stats_list = []

    # エストニア語
    est_path = BASE / "wordlists" / "estonian.txt"
    if est_path.exists():
        print("エストニア語を読み込み中...")
        est_words = load_epitran_words(est_path, "est-Latn")
        stats_list.append(PhonemeStats("Estonian", est_words))

    # クロアチア語
    hrv_path = BASE / "wordlists" / "croatian.txt"
    if hrv_path.exists():
        print("クロアチア語を読み込み中...")
        hrv_words = load_epitran_words(hrv_path, "hrv-Latn")
        stats_list.append(PhonemeStats("Croatian", hrv_words))

    # コノメノ
    kono_path = KONO_BASE / "kono-dictionary-editor" / "dist" / "konomeno-slime.json"
    if kono_path.exists():
        print("コノメノを読み込み中...")
        kono_words = load_kono_words(kono_path)
        stats_list.append(PhonemeStats("Konomeno", kono_words))

    # サイメノ
    sai_path = KONO_BASE / "ref" / "kono-phonology" / "dict" / "saimeno-v4.json"
    if sai_path.exists():
        print("サイメノを読み込み中...")
        sai_words = load_kono_words(sai_path)
        stats_list.append(PhonemeStats("Saimeno", sai_words))

    # --- レポート ---
    for st in stats_list:
        print_report(st)

    # --- 比較サマリー ---
    print("\n\n" + "=" * 60)
    print("  比較サマリー")
    print("=" * 60)
    header = f"  {'':12s} {'語数':>6s} {'token':>7s} {'音素数':>6s} {'H(X)':>7s} {'H_max':>7s} {'H/H_max':>7s} {'H_cond':>7s} {'MI':>7s}"
    print(header)
    print("  " + "-" * 72)
    for st in stats_list:
        s = st.summary_dict()
        ratio = s["H_unigram"] / s["H_max"] if s["H_max"] > 0 else 0
        print(f"  {s['name']:12s} {s['n_words']:6d} {s['n_tokens']:7d} {s['n_phonemes']:6d} "
              f"{s['H_unigram']:7.3f} {s['H_max']:7.3f} {ratio:7.3f} {s['H_cond']:7.3f} {s['MI']:7.3f}")

    # --- プロット ---
    print("\nプロットを生成中...")
    plot_frequency_comparison(stats_list, output_dir)
    print(f"  → {output_dir / 'freq_comparison.png'}")

    plot_entropy_comparison(stats_list, output_dir)
    print(f"  → {output_dir / 'entropy_comparison.png'}")

    for st in stats_list:
        plot_transition_heatmap(st, output_dir)
        print(f"  → {output_dir / f'transition_{st.name}.png'}")
        plot_pmi_heatmap(st, output_dir)
        print(f"  → {output_dir / f'pmi_{st.name}.png'}")


if __name__ == "__main__":
    main()
