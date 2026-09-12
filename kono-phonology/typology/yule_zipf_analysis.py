"""
Tambovtsev & Martindale (2007) の音韻版Zipf/Yule分布検証
saimeno-v4.json と konomeno-v5-zpdic.json の音素頻度分布を
4つのモデルでフィッティングし、R²を比較する。

モデル:
  (1) Zipf:   F_r = a / r^b
  (2) Yule:   F_r = (a / r^b) * c^r
  (3) Sigurd: F_r = (1-k) * k^(r-1) / (1-k^n)   (正規化済み頻度)
  (4) Borodovsky & Gusein-Zade: F_r = (1/n)(log(n+1) - log(r))  (パラメータなし)

注: 論文はコーパス（running text）の音素トークン頻度を使用。
    本分析は辞書の語彙（type）から音素頻度を集計している。
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "Hiragino Sans"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonemes import tokenize, load_zpdic_entries


def extract_phonemes(words):
    phonemes = []
    for w in words:
        ph = tokenize(w)
        if ph is not None:
            phonemes.extend(ph)
    return phonemes


def ranked_frequency(phonemes):
    counts = Counter(phonemes)
    total = sum(counts.values())
    ranked = sorted(counts.values(), reverse=True)
    freqs = np.array(ranked) / total
    ranks = np.arange(1, len(freqs) + 1)
    return ranks, freqs, counts, total


# --- モデル定義 ---

def zipf_model(r, a, b):
    return a / np.power(r, b)


def yule_model(r, a, b, c):
    return (a / np.power(r, b)) * np.power(c, r)


def sigurd_model(r, k, n):
    return (1 - k) * np.power(k, r - 1) / (1 - np.power(k, n))


def borodovsky_gz(r, n):
    return (1 / n) * (np.log(n + 1) - np.log(r))


# --- フィッティング ---

def fit_zipf(ranks, freqs):
    try:
        popt, _ = curve_fit(zipf_model, ranks, freqs, p0=[freqs[0], 1.0], maxfev=10000)
        pred = zipf_model(ranks, *popt)
        r2 = r_squared(freqs, pred)
        return popt, pred, r2
    except Exception:
        return None, None, None


def fit_yule(ranks, freqs):
    try:
        popt, _ = curve_fit(yule_model, ranks, freqs,
                            p0=[freqs[0], 0.5, 0.95],
                            bounds=([0, 0, 0], [np.inf, 5, 1.0]),
                            maxfev=50000)
        pred = yule_model(ranks, *popt)
        r2 = r_squared(freqs, pred)
        return popt, pred, r2
    except Exception:
        return None, None, None


def fit_sigurd(ranks, freqs):
    n = len(ranks)
    try:
        popt, _ = curve_fit(lambda r, k: sigurd_model(r, k, n), ranks, freqs,
                            p0=[0.9], bounds=([0.01], [0.9999]), maxfev=10000)
        pred = sigurd_model(ranks, popt[0], n)
        r2 = r_squared(freqs, pred)
        return (popt[0], n), pred, r2
    except Exception:
        return None, None, None


def calc_borodovsky(ranks, freqs):
    n = len(ranks)
    pred = borodovsky_gz(ranks, n)
    r2 = r_squared(freqs, pred)
    return n, pred, r2


def r_squared(observed, predicted):
    ss_res = np.sum((observed - predicted) ** 2)
    ss_tot = np.sum((observed - np.mean(observed)) ** 2)
    return 1 - ss_res / ss_tot


# --- log-logでのR² ---

def r_squared_loglog(observed, predicted):
    mask = (observed > 0) & (predicted > 0)
    log_obs = np.log(observed[mask])
    log_pred = np.log(predicted[mask])
    ss_res = np.sum((log_obs - log_pred) ** 2)
    ss_tot = np.sum((log_obs - np.mean(log_obs)) ** 2)
    return 1 - ss_res / ss_tot


# --- 分析実行 ---

def analyze_dict(name, words, output_dir):
    phonemes = extract_phonemes(words)
    ranks, freqs, counts, total = ranked_frequency(phonemes)
    n_phonemes = len(ranks)

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  語数: {len(words)}")
    print(f"  総音素トークン数: {total}")
    print(f"  音素種類数 (n): {n_phonemes}")
    print()

    print("  音素頻度 (rank順):")
    sorted_ph = counts.most_common()
    print(sorted_ph)
    for i, (ph, cnt) in enumerate(sorted_ph, 1):
        print(f"    {i:2d}. {ph:3s}  {cnt:5d}  ({cnt/total:.4f})")
    print()

    # フィッティング
    results = {}

    popt, pred, r2 = fit_zipf(ranks, freqs)
    if r2 is not None:
        results["Zipf"] = {"params": popt, "pred": pred, "R2": r2,
                           "R2_loglog": r_squared_loglog(freqs, pred)}
        print(f"  Zipf:     R² = {r2:.4f}  (a={popt[0]:.4f}, b={popt[1]:.4f})")

    popt, pred, r2 = fit_yule(ranks, freqs)
    if r2 is not None:
        results["Yule"] = {"params": popt, "pred": pred, "R2": r2,
                           "R2_loglog": r_squared_loglog(freqs, pred)}
        print(f"  Yule:     R² = {r2:.4f}  (a={popt[0]:.4f}, b={popt[1]:.4f}, c={popt[2]:.4f})")

    popt, pred, r2 = fit_sigurd(ranks, freqs)
    if r2 is not None:
        results["Sigurd"] = {"params": popt, "pred": pred, "R2": r2,
                             "R2_loglog": r_squared_loglog(freqs, pred)}
        k = popt[0]
        print(f"  Sigurd:   R² = {r2:.4f}  (k={k:.4f})")

    n_param, pred, r2 = calc_borodovsky(ranks, freqs)
    if r2 is not None:
        results["Borodovsky"] = {"params": n_param, "pred": pred, "R2": r2,
                                 "R2_loglog": r_squared_loglog(freqs, pred)}
        print(f"  Borodovsky & Gusein-Zade: R² = {r2:.4f}  (パラメータなし, n={n_param})")

    print()

    # --- プロット ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 線形プロット
    ax = axes[0]
    ax.scatter(ranks, freqs, color="black", s=30, zorder=5, label="観測値")
    styles = {"Zipf": ("--", "tab:red"), "Yule": ("-", "tab:blue"),
              "Sigurd": ("-.", "tab:green"), "Borodovsky": (":", "tab:orange")}
    for model_name, res in results.items():
        ls, color = styles[model_name]
        label = f"{model_name} (R²={res['R2']:.3f})"
        ax.plot(ranks, res["pred"], ls, color=color, linewidth=1.5, label=label)
    ax.set_xlabel("Rank")
    ax.set_ylabel("Relative Frequency")
    ax.set_title(f"{name} — 音素頻度分布")
    ax.legend(fontsize=8)

    # log-logプロット (論文Figure 1と同じ形式)
    ax = axes[1]
    ax.scatter(np.log(ranks), np.log(freqs), color="black", s=30, zorder=5, label="観測値")
    for model_name, res in results.items():
        ls, color = styles[model_name]
        pred = res["pred"]
        mask = pred > 0
        label = f"{model_name} (R²_loglog={res['R2_loglog']:.3f})"
        ax.plot(np.log(ranks[mask]), np.log(pred[mask]), ls, color=color,
                linewidth=1.5, label=label)
    ax.set_xlabel("Log Rank")
    ax.set_ylabel("Log Frequency")
    ax.set_title(f"{name} — log-log プロット")
    ax.legend(fontsize=8)

    plt.tight_layout()
    out_path = output_dir / f"{name.replace(' ', '_')}_fit.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  → 図を保存: {out_path}")

    return results


def main():
    base = Path(__file__).resolve().parent.parent.parent
    dict_dir = base / "ref" / "kono-phonology" / "dict"
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)

    saimeno_words = load_zpdic_entries(dict_dir / "saimeno-v4.json")
    konomeno_words = load_zpdic_entries(dict_dir / "konomeno-v5-zpdic.json")

    print("Tambovtsev & Martindale (2007) 音韻版 Zipf/Yule 分布検証")
    print("=" * 60)

    r1 = analyze_dict("saimeno-v4", saimeno_words, output_dir)
    r2 = analyze_dict("konomeno-v5", konomeno_words, output_dir)

    # 比較サマリー
    print("\n" + "=" * 60)
    print("  比較サマリー")
    print("=" * 60)
    print(f"{'モデル':20s} {'saimeno R²':>12s} {'konomeno R²':>12s}  {'論文平均R²':>10s}")
    print("-" * 60)
    ref_r2 = {"Zipf": 0.90, "Yule": 0.97, "Sigurd": 0.93, "Borodovsky": 0.95}
    for model in ["Zipf", "Sigurd", "Borodovsky", "Yule"]:
        s1 = f"{r1[model]['R2']:.4f}" if model in r1 and r1[model]["R2"] is not None else "N/A"
        s2 = f"{r2[model]['R2']:.4f}" if model in r2 and r2[model]["R2"] is not None else "N/A"
        ref = f"{ref_r2[model]:.2f}"
        print(f"  {model:18s} {s1:>12s} {s2:>12s}  {ref:>10s}")

    # 比較プロット
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, (name, results) in zip(axes, [("saimeno-v4", r1), ("konomeno-v5", r2)]):
        models = list(results.keys())
        r2_vals = [results[m]["R2"] for m in models]
        ref_vals = [ref_r2[m] for m in models]
        x = np.arange(len(models))
        w = 0.35
        ax.bar(x - w/2, r2_vals, w, label=name, color="tab:blue")
        ax.bar(x + w/2, ref_vals, w, label="論文平均 (95言語)", color="tab:orange", alpha=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(models)
        ax.set_ylabel("R²")
        ax.set_title(name)
        ax.set_ylim(0.7, 1.02)
        ax.legend()
        for i, (v1, v2) in enumerate(zip(r2_vals, ref_vals)):
            ax.text(i - w/2, v1 + 0.005, f"{v1:.3f}", ha="center", fontsize=8)
            ax.text(i + w/2, v2 + 0.005, f"{v2:.2f}", ha="center", fontsize=8)
    plt.suptitle("Tambovtsev & Martindale (2007) 再現: 人工言語 vs 自然言語平均", fontsize=12)
    plt.tight_layout()
    plt.savefig(output_dir / "comparison.png", dpi=150)
    plt.close()
    print(f"\n  → 比較図を保存: {output_dir / 'comparison.png'}")


if __name__ == "__main__":
    main()
