"""
Tambovtsev & Martindale (2007) 追加分析:
  A) rank<=10 の音素のみでフィッティング（全単語から集計、上位10音素で切る）
  B) rank<=10 の音素のみで構成された単語だけで分布を作ってフィッティング
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Hiragino Sans"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonemes import tokenize as _tokenize, load_zpdic_entries as load_words


def tokenize(w):
    return _tokenize(w) or []


def zipf_model(r, a, b):
    return a / np.power(r, b)

def yule_model(r, a, b, c):
    return (a / np.power(r, b)) * np.power(c, r)

def sigurd_model(r, k, n):
    return (1 - k) * np.power(k, r - 1) / (1 - np.power(k, n))

def borodovsky_gz(r, n):
    return (1 / n) * (np.log(n + 1) - np.log(r))

def r_squared(obs, pred):
    ss_res = np.sum((obs - pred) ** 2)
    ss_tot = np.sum((obs - np.mean(obs)) ** 2)
    return 1 - ss_res / ss_tot


def fit_all(ranks, freqs):
    results = {}
    n = len(ranks)

    try:
        popt, _ = curve_fit(zipf_model, ranks, freqs, p0=[freqs[0], 1.0], maxfev=10000)
        pred = zipf_model(ranks, *popt)
        results["Zipf"] = {"R2": r_squared(freqs, pred), "pred": pred,
                           "label": f"a={popt[0]:.4f}, b={popt[1]:.4f}"}
    except Exception:
        pass

    try:
        popt, _ = curve_fit(yule_model, ranks, freqs,
                            p0=[freqs[0], 0.5, 0.95],
                            bounds=([0, 0, 0], [np.inf, 5, 1.0]), maxfev=50000)
        pred = yule_model(ranks, *popt)
        results["Yule"] = {"R2": r_squared(freqs, pred), "pred": pred,
                           "label": f"a={popt[0]:.4f}, b={popt[1]:.4f}, c={popt[2]:.4f}"}
    except Exception:
        pass

    try:
        popt, _ = curve_fit(lambda r, k: sigurd_model(r, k, n), ranks, freqs,
                            p0=[0.9], bounds=([0.01], [0.9999]), maxfev=10000)
        pred = sigurd_model(ranks, popt[0], n)
        results["Sigurd"] = {"R2": r_squared(freqs, pred), "pred": pred,
                             "label": f"k={popt[0]:.4f}"}
    except Exception:
        pass

    pred = borodovsky_gz(ranks, n)
    results["Borodovsky"] = {"R2": r_squared(freqs, pred), "pred": pred,
                             "label": f"n={n}"}

    return results


def analyze(name, words, mode, output_dir):
    all_phs = [(w, tokenize(w)) for w in words]
    all_phonemes = [ph for _, phs in all_phs for ph in phs]
    global_counts = Counter(all_phonemes)
    top10 = [ph for ph, _ in global_counts.most_common(10)]
    top10_set = set(top10)

    if mode == "truncate":
        counts = {ph: c for ph, c in global_counts.items() if ph in top10_set}
        total = sum(counts.values())
        ranked = sorted(counts.values(), reverse=True)
        subtitle = "rank 10以下の音素のみでフィッティング"
        n_words = len(words)
        extra_info = f"(全{len(global_counts)}音素中 上位10音素, トークン {total}/{sum(global_counts.values())})"
    else:
        filtered_words = []
        for w, phs in all_phs:
            if phs and all(ph in top10_set for ph in phs):
                filtered_words.append((w, phs))
        phonemes = [ph for _, phs in filtered_words for ph in phs]
        counts_c = Counter(phonemes)
        counts = dict(counts_c.most_common())
        total = sum(counts.values())
        ranked = sorted(counts.values(), reverse=True)
        n_words = len(filtered_words)
        subtitle = "上位10音素のみの単語でフィッティング"
        extra_info = f"({n_words}/{len(words)} 語が該当, トークン {total})"

    freqs = np.array(ranked) / total
    ranks = np.arange(1, len(freqs) + 1)
    n_ph = len(ranks)

    print(f"\n{'='*60}")
    print(f"  {name} — {subtitle}")
    print(f"{'='*60}")
    print(f"  {extra_info}")
    print(f"  使用語数: {n_words}, 音素種類数: {n_ph}")
    print()

    sorted_ph = sorted(counts.items(), key=lambda x: -x[1])
    for i, (ph, cnt) in enumerate(sorted_ph, 1):
        print(f"    {i:2d}. {ph:3s}  {cnt:5d}  ({cnt/total:.4f})")
    print()

    if mode == "filter":
        excluded = [w for w, phs in all_phs
                    if phs and not all(ph in top10_set for ph in phs)]
        if excluded:
            minor_usage = Counter()
            for w, phs in all_phs:
                if phs and not all(ph in top10_set for ph in phs):
                    for ph in phs:
                        if ph not in top10_set:
                            minor_usage[ph] += 1
            print(f"  除外された単語: {len(excluded)} 語")
            print(f"  除外理由のマイナー音素使用数:")
            for ph, c in minor_usage.most_common():
                print(f"    {ph:3s}: {c} 回")
            print()

    results = fit_all(ranks, freqs)
    for m in ["Zipf", "Yule", "Sigurd", "Borodovsky"]:
        if m in results:
            print(f"  {m:12s}: R² = {results[m]['R2']:.4f}  ({results[m]['label']})")

    # プロット
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    styles = {"Zipf": ("--", "tab:red"), "Yule": ("-", "tab:blue"),
              "Sigurd": ("-.", "tab:green"), "Borodovsky": (":", "tab:orange")}

    ax = axes[0]
    ax.scatter(ranks, freqs, color="black", s=30, zorder=5, label="観測値")
    for mn, res in results.items():
        ls, color = styles[mn]
        ax.plot(ranks, res["pred"], ls, color=color, linewidth=1.5,
                label=f"{mn} (R²={res['R2']:.3f})")
    ax.set_xlabel("Rank")
    ax.set_ylabel("Relative Frequency")
    ax.set_title(f"{name}\n{subtitle}")
    ax.legend(fontsize=8)

    ax = axes[1]
    ax.scatter(np.log(ranks), np.log(freqs), color="black", s=30, zorder=5, label="観測値")
    for mn, res in results.items():
        ls, color = styles[mn]
        pred = res["pred"]
        mask = pred > 0
        ax.plot(np.log(ranks[mask]), np.log(pred[mask]), ls, color=color,
                linewidth=1.5, label=f"{mn} (R²={res['R2']:.3f})")
    ax.set_xlabel("Log Rank")
    ax.set_ylabel("Log Frequency")
    ax.set_title(f"{name} — log-log\n{subtitle}")
    ax.legend(fontsize=8)

    plt.tight_layout()
    tag = "truncate" if mode == "truncate" else "filter"
    out_path = output_dir / f"{name.replace(' ', '_')}_{tag}.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"\n  → {out_path}")
    return results


def main():
    base = Path(__file__).resolve().parent.parent.parent
    dict_dir = base / "ref" / "kono-phonology" / "dict"
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)

    dicts = {
        "saimeno-v4": load_words(dict_dir / "saimeno-v4.json"),
        "konomeno-v5": load_words(dict_dir / "konomeno-v5-zpdic.json"),
    }

    all_results = {}
    for name, words in dicts.items():
        for mode in ["truncate", "filter"]:
            key = f"{name}_{mode}"
            all_results[key] = analyze(name, words, mode, output_dir)

    # 比較テーブル
    print("\n\n" + "=" * 80)
    print("  全条件比較")
    print("=" * 80)
    header = f"{'':30s}"
    for m in ["Zipf", "Yule", "Sigurd", "Borodovsky"]:
        header += f" {m:>10s}"
    print(header)
    print("-" * 80)
    for key in all_results:
        row = f"  {key:28s}"
        for m in ["Zipf", "Yule", "Sigurd", "Borodovsky"]:
            r2 = all_results[key].get(m, {}).get("R2")
            row += f" {r2:10.4f}" if r2 is not None else f" {'N/A':>10s}"
        print(row)

    # 前回の全体結果も再掲用に表示
    print()
    print("  参考: 全音素での結果 (前回分析)")
    print("  saimeno-v4  全体           Zipf=0.8176  Yule=0.9674  Sigurd=0.9668  Borodovsky=0.9232")
    print("  konomeno-v5 全体           Zipf=0.8169  Yule=0.9734  Sigurd=0.9724  Borodovsky=0.9143")

    # 6条件比較棒グラフ
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    models = ["Zipf", "Yule", "Sigurd", "Borodovsky"]

    full_results = {
        "saimeno-v4_full": {"Zipf": {"R2": 0.8176}, "Yule": {"R2": 0.9674},
                            "Sigurd": {"R2": 0.9668}, "Borodovsky": {"R2": 0.9232}},
        "konomeno-v5_full": {"Zipf": {"R2": 0.8169}, "Yule": {"R2": 0.9734},
                             "Sigurd": {"R2": 0.9724}, "Borodovsky": {"R2": 0.9143}},
    }
    all_results.update(full_results)

    for ax_idx, dict_name in enumerate(["saimeno-v4", "konomeno-v5"]):
        ax = axes[ax_idx, 0]
        conditions = ["full", "truncate", "filter"]
        labels = ["全音素 (27)", "rank 10以下\n切り詰め", "top10音素\nのみの語"]
        x = np.arange(len(models))
        w = 0.25
        colors = ["tab:blue", "tab:green", "tab:red"]
        for ci, (cond, lab, col) in enumerate(zip(conditions, labels, colors)):
            key = f"{dict_name}_{cond}"
            vals = [all_results[key].get(m, {}).get("R2", 0) for m in models]
            ax.bar(x + (ci - 1) * w, vals, w, label=lab, color=col, alpha=0.8)
            for i, v in enumerate(vals):
                ax.text(i + (ci - 1) * w, v + 0.003, f"{v:.3f}", ha="center", fontsize=6.5)
        ax.set_xticks(x)
        ax.set_xticklabels(models)
        ax.set_ylabel("R²")
        ax.set_title(dict_name)
        ax.set_ylim(0.7, 1.05)
        ax.legend(fontsize=8)

        # 音素分布の差を可視化
        ax = axes[ax_idx, 1]
        words = dicts[dict_name]
        all_phs_list = [tokenize(w) for w in words]
        all_phonemes = [ph for phs in all_phs_list for ph in phs]
        gc = Counter(all_phonemes)
        top10_set = set(ph for ph, _ in gc.most_common(10))
        sorted_all = gc.most_common()
        ph_names = [ph for ph, _ in sorted_all]
        ph_counts = [c for _, c in sorted_all]
        bar_colors = ["tab:blue" if ph in top10_set else "tab:red" for ph in ph_names]
        ax.bar(range(len(ph_names)), ph_counts, color=bar_colors)
        ax.set_xticks(range(len(ph_names)))
        ax.set_xticklabels(ph_names, fontsize=7)
        ax.set_ylabel("出現数")
        ax.set_title(f"{dict_name} — 音素頻度 (青=top10, 赤=rank>10)")
        cumsum = np.cumsum(ph_counts) / sum(ph_counts) * 100
        ax2 = ax.twinx()
        ax2.plot(range(len(ph_names)), cumsum, "k--", linewidth=1, alpha=0.5)
        ax2.set_ylabel("累積 %")
        ax2.axhline(cumsum[9], color="gray", linestyle=":", linewidth=0.8)
        ax2.text(len(ph_names) - 1, cumsum[9] + 1, f"{cumsum[9]:.1f}%", fontsize=8, color="gray")

    plt.suptitle("条件別 R² 比較 + 音素頻度分布", fontsize=13)
    plt.tight_layout()
    plt.savefig(output_dir / "top10_comparison.png", dpi=150)
    plt.close()
    print(f"\n  → {output_dir / 'top10_comparison.png'}")


if __name__ == "__main__":
    main()
