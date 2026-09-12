"""音声測定 — 手順 C.

キャリア文（``X kino danktai``）で読み上げた連続録音を、刺激リストに
対応づけて音節ごとの f0・持続時間を取り出す．

# 全体の流れ

1. **発話の切り出し** … 強度包絡の無音で分割する
2. **刺激リストとの対応づけ** … 分割の過不足（読み手が語中で間を置くと
   1発話が2つに割れる）を持続時間モデルで検出して統合／削除する
3. **キャリアの検出** … キャリア文は全発話で同一なので、平均スペクトル
   テンプレートとの照合で「目標語の終端＝キャリアの始端」を求める．
   これが本モジュールの要で、音素認識をせずに目標語の区間が確定する
4. **音節への分割** … 目標語の音節数は既知なので、区間内の強度の谷を
   動的計画法で n-1 本選ぶ（自由な音節検出より遥かに安定する）
5. **測定** … 音節ごとに f0（開始・中央・終端・傾き・レンジ）と持続時間
6. **TextGrid 出力** … 自動区間を Praat で手修正できるようにする

# なぜキャリア文が効くか

引用形（単独読み）では、語末の上昇 R が語彙的なアクセントなのか発話末の
境界上昇なのかが原理的に区別できない．キャリア文では目標語が句頭に来て
発話末は常に ``danktai`` なので、**目標語の語末に R が残るかどうか**で
この 2 つを切り分けられる．``phonology.tex`` の保留項目そのものである．

必要なもの: ``praat-parselmouth``（``pip install praat-parselmouth``）．
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

try:
    import parselmouth
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "音声測定には parselmouth が必要です: pip install praat-parselmouth"
    ) from _e

from .word import Word

Interval = tuple[float, float]


# ---------------------------------------------------------------------------
# 録音
# ---------------------------------------------------------------------------


@dataclass
class Recording:
    """1 本の録音．強度・ピッチ・スペクトル特徴を一度だけ計算して持つ."""

    path: Path
    sound: "parselmouth.Sound"
    time_step: float = 0.01
    pitch_floor: float = 60.0
    pitch_ceiling: float = 400.0

    @classmethod
    def load(cls, path: str | Path, **kw) -> "Recording":
        p = Path(path)
        snd = parselmouth.Sound(str(p))
        if snd.n_channels > 1:
            snd = snd.convert_to_mono()
        r = cls(path=p, sound=snd, **kw)
        r._prepare()
        return r

    def _prepare(self):
        it = self.sound.to_intensity(time_step=self.time_step, minimum_pitch=60)
        self.itime = np.asarray(it.xs())
        v = np.asarray(it.values[0], dtype=float)
        finite = np.isfinite(v)
        v[~finite] = v[finite].min() if finite.any() else 0.0
        self.intensity = v
        pt = self.sound.to_pitch(
            time_step=self.time_step,
            pitch_floor=self.pitch_floor,
            pitch_ceiling=self.pitch_ceiling,
        )
        self.ptime = np.asarray(pt.xs())
        f = pt.selected_array["frequency"].astype(float).copy()
        f[f == 0] = np.nan
        self.f0 = f
        self.samples = np.asarray(self.sound.values[0], dtype=float)
        self.sr = float(self.sound.sampling_frequency)
        self._prepare_bands()

    def _prepare_bands(self, n_bands: int = 24, hop: float = 0.01):
        """帯域エネルギーを録音全体で一度だけ計算しておく.

        テンプレート照合は「開始位置をずらしながら何百回も特徴を取る」ので、
        呼ばれるたびにスペクトログラムを計算すると全く終わらない．
        全体を一度求めておき、以後は行列の切り出しとリサンプルだけにする．
        """
        from scipy.signal import spectrogram

        nper = int(self.sr * 0.025)
        nover = nper - int(self.sr * hop)
        f, t, S = spectrogram(self.samples, self.sr, nperseg=nper, noverlap=nover)
        S = np.log(S + 1e-10)
        edges = np.linspace(80, 4000, n_bands + 1)
        B = np.stack([S[(f >= edges[j]) & (f < edges[j + 1])].mean(axis=0) for j in range(n_bands)])
        self.band_energy = B          # (n_bands, n_frames)
        self.band_time = t
        self.n_bands = n_bands
        # 強度フレームごとの有声性（split_syllables で多用するので先に作る）
        vt = np.interp(self.itime, self.ptime, np.isfinite(self.f0).astype(float),
                       left=0.0, right=0.0)
        self.voiced_at_itime = vt

    # -- 便利 -----------------------------------------------------------
    @property
    def duration(self) -> float:
        return float(self.sound.duration)

    def intensity_in(self, a: float, b: float) -> tuple[np.ndarray, np.ndarray]:
        m = (self.itime >= a) & (self.itime <= b)
        return self.itime[m], self.intensity[m]

    def f0_in(self, a: float, b: float) -> tuple[np.ndarray, np.ndarray]:
        m = (self.ptime >= a) & (self.ptime <= b)
        t, f = self.ptime[m], self.f0[m]
        ok = np.isfinite(f)
        return t[ok], f[ok]

    def voiced_fraction(self, a: float, b: float) -> float:
        m = (self.ptime >= a) & (self.ptime <= b)
        return float(np.isfinite(self.f0[m]).mean()) if m.any() else 0.0

    # -- スペクトル特徴（テンプレート照合用） -----------------------------
    def spectral_feature(self, a: float, b: float, n_frames: int = 12):
        """区間 [a,b] を時間方向 ``n_frames`` に正規化した帯域エネルギー特徴.

        時間正規化してあるので、長さの違うキャリア実現どうしも比較できる．
        """
        i0 = int(np.searchsorted(self.band_time, a))
        i1 = int(np.searchsorted(self.band_time, b))
        if i1 - i0 < n_frames:
            return None
        edges = np.linspace(i0, i1, n_frames + 1).astype(int)
        M = np.stack([self.band_energy[:, e0:e1].mean(axis=1) for e0, e1 in zip(edges[:-1], edges[1:])])
        v = M.ravel()
        sd = v.std()
        return (v - v.mean()) / (sd if sd > 0 else 1.0)


# ---------------------------------------------------------------------------
# 1. 発話の切り出し
# ---------------------------------------------------------------------------


def segment_utterances(
    rec: Recording,
    *,
    threshold_frac: float = 0.40,
    min_silence: float = 0.35,
    min_duration: float = 0.35,
) -> list[Interval]:
    """強度包絡の無音で発話を切り出す.

    しきい値は絶対 dB ではなく録音内の分位点（p5〜p95）の比で決める．
    録音レベルが変わっても同じ設定が使えるようにするため．
    """
    v, t = rec.intensity, rec.itime
    lo, hi = np.percentile(v, 5), np.percentile(v, 95)
    thr = lo + (hi - lo) * threshold_frac
    out: list[Interval] = []
    start = last = None
    for tt, on in zip(t, v > thr):
        if on:
            if start is None:
                start = tt
            last = tt
        elif start is not None and tt - last >= min_silence:
            if last - start >= min_duration:
                out.append((start, last))
            start = None
    if start is not None and last - start >= min_duration:
        out.append((start, last))
    return out


# ---------------------------------------------------------------------------
# 2. 刺激リストとの対応づけ
# ---------------------------------------------------------------------------


@dataclass
class Alignment:
    """発話と刺激の対応．"""

    intervals: list[Interval]           # 刺激と同じ長さ
    merged: list[tuple[int, ...]]       # 各刺激に使った元発話の index
    dropped: list[int]                  # 使わなかった元発話の index
    n_utterances: int
    n_stimuli: int

    def report(self) -> str:
        lines = [f"発話 {self.n_utterances} / 刺激 {self.n_stimuli}"]
        m = [(i, g) for i, g in enumerate(self.merged) if len(g) > 1]
        if m:
            lines.append(f"統合した発話（語中で間が空いて分割されたもの）: {len(m)} 件")
            for i, g in m:
                lines.append(f"  刺激 #{i + 1} ← 発話 {[k + 1 for k in g]}")
        if self.dropped:
            lines.append(f"未使用の発話: {[k + 1 for k in self.dropped]}")
        return "\n".join(lines)


def align_utterances(
    utterances: Sequence[Interval],
    expected_syllables: Sequence[int],
    *,
    max_merge: int = 3,
) -> Alignment:
    """発話列を刺激列に単調対応させる.

    持続時間 ≈ 切片 + 傾き × 音節数 というモデルで、隣接発話の統合
    （読み手が語中で間を置いた場合）と発話の削除（余分な読み）を許した
    動的計画法で対応づける．係数はまず素朴な 1:1 対応から推定し、
    対応が求まったら再推定する（2 回）．
    """
    U = [tuple(u) for u in utterances]
    E = list(expected_syllables)
    nU, nE = len(U), len(E)
    dur = np.array([b - a for a, b in U])

    def fit_model(pairs):
        if len(pairs) < 8:
            return 1.2, 0.13
        n = np.array([E[i] for i, _ in pairs], dtype=float)
        d = np.array([g for _, g in pairs], dtype=float)
        A = np.c_[np.ones(len(n)), n]
        coef, *_ = np.linalg.lstsq(A, d, rcond=None)
        return float(coef[0]), float(coef[1])

    m0 = min(nU, nE)
    a0, b0 = fit_model([(i, dur[i]) for i in range(m0)])

    best: list[tuple[int, ...]] | None = None
    for _ in range(2):
        INF = float("inf")
        # cost[i][j] = 刺激 i..、発話 j.. を対応させた最小コスト
        cost = np.full((nE + 1, nU + 1), INF)
        back: dict[tuple[int, int], tuple[int, int, int]] = {}
        cost[nE][nU] = 0.0
        for i in range(nE, -1, -1):
            for j in range(nU, -1, -1):
                if i == nE and j == nU:
                    continue
                bestc, bestb = INF, None
                if i < nE and j < nU:
                    pred = a0 + b0 * E[i]
                    for k in range(1, max_merge + 1):
                        if j + k > nU:
                            break
                        span = U[j + k - 1][1] - U[j][0]
                        c = abs(span - pred) / max(pred, 0.1) + 0.25 * (k - 1)
                        nxt = cost[i + 1][j + k]
                        if nxt < INF and c + nxt < bestc:
                            bestc, bestb = c + nxt, (i + 1, j + k, k)
                if j < nU:  # 発話を捨てる
                    nxt = cost[i][j + 1]
                    if nxt < INF and 1.5 + nxt < bestc:
                        bestc, bestb = 1.5 + nxt, (i, j + 1, 0)
                if bestb is not None:
                    cost[i][j] = bestc
                    back[(i, j)] = bestb
        # 復元
        merged: list[tuple[int, ...]] = []
        dropped: list[int] = []
        i = j = 0
        while (i, j) in back:
            ni, nj, k = back[(i, j)]
            if k == 0:
                dropped.append(j)
            else:
                merged.append(tuple(range(j, j + k)))
            i, j = ni, nj
        if len(merged) != nE:
            break
        best = merged
        a0, b0 = fit_model([(i, U[g[-1]][1] - U[g[0]][0]) for i, g in enumerate(merged)])

    if best is None:  # フォールバック: 素朴な 1:1
        best = [(k,) for k in range(min(nU, nE))]
        dropped = list(range(len(best), nU))
    return Alignment(
        intervals=[(U[g[0]][0], U[g[-1]][1]) for g in best],
        merged=best,
        dropped=sorted(dropped),
        n_utterances=nU,
        n_stimuli=nE,
    )


# ---------------------------------------------------------------------------
# 3. キャリアの検出
# ---------------------------------------------------------------------------


@dataclass
class CarrierModel:
    """キャリア文の平均スペクトルテンプレート."""

    template: np.ndarray
    typical_duration: float
    similarity: np.ndarray = field(default_factory=lambda: np.array([]))

    @classmethod
    def build(
        cls, rec: Recording, intervals: Sequence[Interval], approx_duration: float = 0.75
    ) -> "CarrierModel":
        V = []
        for a, b in intervals:
            v = rec.spectral_feature(max(a, b - approx_duration), b)
            if v is not None:
                V.append(v)
        V = np.stack(V)
        tpl = V.mean(0)
        tpl = (tpl - tpl.mean()) / (tpl.std() or 1.0)
        sim = V @ tpl / V.shape[1]
        return cls(template=tpl, typical_duration=approx_duration, similarity=sim)

    def onset(
        self, rec: Recording, interval: Interval, *, min_target: float = 0.15, step: float = 0.01
    ) -> tuple[float, float]:
        """キャリアの開始時刻とその照合スコアを返す."""
        a, b = interval
        lo = a + min_target
        hi = b - 0.35
        if hi <= lo:
            return (a + (b - a) * 0.4, 0.0)
        best_t, best_s = lo, -1e9
        t = lo
        while t <= hi:
            v = rec.spectral_feature(t, b)
            if v is not None:
                s = float(v @ self.template / len(self.template))
                if s > best_s:
                    best_s, best_t = s, t
            t += step
        return snap_to_closure(rec, best_t, interval), best_s


@dataclass
class FrameCarrier:
    """目標語を前後から挟む枠（``kino X danktai``）用のモデル.

    目標語が句頭にあると句頭の H と declination が語彙アクセントを塗り
    つぶす（2026-08 の録音がそうだった）．句中に置けば句レベルの型が両側で
    固定され、語彙的な寄与が残差として残る．そのぶん境界検出は難しくなる ──
    後続キャリアが有声音で始まると、``kino`` の /k/ のような無声閉鎖の
    手掛かりが使えない．

    そこで **スペクトルテンプレートと持続時間モデルを併用する**:

    ``発話長 ≈ (P + S + α·音節数) · rᵢ``

    P は前置キャリア、S は後置キャリア、α は目標語の1音節あたりの長さ、
    rᵢ は発話ごとの話速係数．P+S と α は全発話の回帰で求まり、
    P と S の内訳は後置キャリアのテンプレート照合（こちらは境界が
    はっきりしていて安定する）から決める．

    テンプレートだけで探すと前置キャリアの境界が一貫して遅れる
    （テンプレートに目標語の頭が混入して自己強化される）ので、
    この持続時間の事前分布が要る．
    """

    prefix: np.ndarray
    suffix: np.ndarray
    prefix_span: float
    suffix_span: float
    syllable_span: float = 0.20
    score: np.ndarray = field(default_factory=lambda: np.array([]))

    # -- 構築 -----------------------------------------------------------
    @classmethod
    def build(
        cls,
        rec: Recording,
        intervals: Sequence[Interval],
        n_syllables: Sequence[int],
        *,
        iterations: int = 3,
        step: float = 0.01,
        duration_weight: float = 1.2,
        carrier_syllables: int = 4,
    ) -> tuple["FrameCarrier", list[tuple[float, float, float]]]:
        """テンプレートを反復改良しつつ、各発話の目標語区間を返す.

        戻り値の 2 番目は ``(target_start, target_end, score)`` のリスト．
        """
        # 持続時間の事前分布は「音節数の按分」で作る．
        # 発話長の回帰（切片＋傾き）は 3 音節語が 8 割を占めていて傾きが
        # ほとんど決まらず、目標語を極端に短く見積もってしまうため使わない．
        # キャリアも目標語も同じ話速で読まれると仮定し、キャリアの音節数
        # （kino 2 + danktai 2 = 4）で発話長を割って 1 音節あたりを出す．
        n_arr = np.array(n_syllables, dtype=float)
        dur = np.array([b - a for a, b in intervals], dtype=float)
        rate = dur / (n_arr + carrier_syllables)
        alpha = float(np.median(rate))
        # キャリアは句末長音化などで目標語より長くなりうるので重みで持つ
        wp = ws = carrier_syllables / 2.0
        P, S = wp * alpha, ws * alpha

        model = cls(np.zeros(1), np.zeros(1), P, S, alpha)
        bounds = [
            model._prior_bounds(iv, k) for iv, k in zip(intervals, n_syllables)
        ]
        for _ in range(iterations):
            model._fit_templates(rec, intervals, bounds)
            bounds = [
                model._locate(rec, iv, k, step=step, duration_weight=duration_weight)
                for iv, k in zip(intervals, n_syllables)
            ]
            model.prefix_span = float(np.median([t0 - a for (t0, _t1, _s), (a, _b) in zip(bounds, intervals)]))
            model.suffix_span = float(np.median([b - t1 for (_t0, t1, _s), (_a, b) in zip(bounds, intervals)]))
            obs = float(np.median([(t1 - t0) / max(k, 1) for (t0, t1, _s), k in zip(bounds, n_syllables)]))
            # 事前分布から離れすぎないようにする（テンプレートの自己強化で
            # 目標語が痩せ細るのを防ぐ）
            model.syllable_span = float(np.clip(obs, alpha * 0.75, alpha * 1.6))
            model.prefix_span = float(np.clip(model.prefix_span, alpha * 0.9, alpha * 3.2))
            model.suffix_span = float(np.clip(model.suffix_span, alpha * 0.9, alpha * 3.2))
        model.score = np.array([s for _a, _b, s in bounds])
        return model, bounds

    # -- 内部 -----------------------------------------------------------
    def _rate(self, interval: Interval, n_syl: int) -> float:
        a, b = interval
        want = self.prefix_span + self.suffix_span + self.syllable_span * n_syl
        return (b - a) / want if want > 0 else 1.0

    def _prior_bounds(self, interval: Interval, n_syl: int) -> tuple[float, float, float]:
        a, b = interval
        k = self._rate(interval, n_syl)
        return (a + self.prefix_span * k, b - self.suffix_span * k, 0.0)

    def _fit_templates(self, rec, intervals, bounds):
        """テンプレートは境界の内側 85% だけから作る（目標語の混入を防ぐ）."""
        P, S = [], []
        for (a, b), (t0, t1, _s) in zip(intervals, bounds):
            vp = rec.spectral_feature(a, a + (t0 - a) * 0.85)
            vs = rec.spectral_feature(b - (b - t1) * 0.85, b)
            if vp is not None:
                P.append(vp)
            if vs is not None:
                S.append(vs)

        def norm(V, fallback):
            if not V:
                return fallback
            m = np.stack(V).mean(0)
            return (m - m.mean()) / (m.std() or 1.0)

        self.prefix = norm(P, self.prefix)
        self.suffix = norm(S, self.suffix)

    def _locate(
        self,
        rec: Recording,
        interval: Interval,
        n_syl: int,
        *,
        step: float = 0.01,
        duration_weight: float = 1.2,
    ) -> tuple[float, float, float]:
        a, b = interval
        if len(self.prefix) < 2 or len(self.suffix) < 2:
            return self._prior_bounds(interval, n_syl)
        k = self._rate(interval, n_syl)
        want_p = self.prefix_span * k
        want_s = self.suffix_span * k
        want_t = self.syllable_span * n_syl * k

        g1 = np.arange(max(a + 0.08, a + want_p * 0.45), min(b - 0.25, a + want_p * 1.7) + 1e-9, step)
        g2 = np.arange(max(a + 0.25, b - want_s * 1.7), min(b - 0.08, b - want_s * 0.45) + 1e-9, step)
        if len(g1) == 0 or len(g2) == 0:
            return self._prior_bounds(interval, n_syl)
        s1 = np.array([self._sim(rec, a, t, self.prefix) for t in g1])
        s2 = np.array([self._sim(rec, t, b, self.suffix) for t in g2])

        T1, T2 = np.meshgrid(g1, g2, indexing="ij")
        pen = (
            np.abs((T1 - a) - want_p) / max(want_p, 0.05)
            + np.abs((b - T2) - want_s) / max(want_s, 0.05)
            + np.abs((T2 - T1) - want_t) / max(want_t, 0.05)
        )
        total = s1[:, None] + s2[None, :] - duration_weight * pen
        total[(T2 - T1) < 0.06 * n_syl] = -1e9
        i, j = np.unravel_index(int(np.argmax(total)), total.shape)
        t0 = snap_to_dip(rec, float(g1[i]))
        t1 = snap_to_dip(rec, float(g2[j]))
        if t1 - t0 < 0.06 * n_syl:
            t0, t1 = float(g1[i]), float(g2[j])
        return (t0, t1, float((s1[i] + s2[j]) / 2))

    @staticmethod
    def _sim(rec: Recording, a: float, b: float, tpl: np.ndarray) -> float:
        v = rec.spectral_feature(a, b)
        if v is None or len(v) != len(tpl):
            return -1.0
        return float(v @ tpl / len(tpl))


def snap_to_dip(rec: Recording, t: float, *, window: float = 0.06) -> float:
    """境界候補を近傍の強度極小に吸着させる.

    後続キャリアが有声音で始まる枠（``danktai``）では無声閉鎖の手掛かりが
    無いので、閉鎖ではなく強度の谷に合わせる．
    """
    m = (rec.itime >= t - window) & (rec.itime <= t + window)
    if not m.any():
        return t
    tt, vv = rec.itime[m], rec.intensity[m]
    return float(tt[int(np.argmin(vv))])


def snap_to_closure(
    rec: Recording, t: float, interval: Interval, *, back: float = 0.22, fwd: float = 0.08
) -> float:
    """テンプレート照合の結果を直前の閉鎖区間の始まりに吸着させる.

    キャリアは ``kino`` すなわち無声破裂音 /k/ で始まるので、目標語の終端の
    直後には必ず「無声かつ低強度」の閉鎖区間がある．テンプレート照合は
    時間正規化しているぶん閉鎖区間の中で止まりやすく、境界が一貫して
    数十〜200ms 遅れる．そこで照合位置の手前にある無声区間を探し、
    その**始端**（＝直前の母音の終わり）を境界とする．
    """
    a, b = interval
    lo, hi = max(a + 0.05, t - back), min(b - 0.05, t + fwd)
    m = (rec.itime >= lo) & (rec.itime <= hi)
    if not m.any():
        return t
    tt = rec.itime[m]
    voiced = rec.voiced_at_itime[m]
    iv = rec.intensity[m]
    thr = np.percentile(rec.intensity, 5) + (
        np.percentile(rec.intensity, 95) - np.percentile(rec.intensity, 5)
    ) * 0.55
    closed = (voiced < 0.5) | (iv < thr)
    # 末尾側から見て、連続する閉鎖のかたまりの始端を返す
    idx = np.where(closed)[0]
    if len(idx) == 0:
        return t
    end = idx[-1]
    start = end
    while start - 1 >= 0 and closed[start - 1]:
        start -= 1
    if end - start < 1:  # 単発のノイズは無視
        return t
    return float(tt[start])


# ---------------------------------------------------------------------------
# 4. 音節への分割（音節数既知の制約つき）
# ---------------------------------------------------------------------------


def split_syllables(
    rec: Recording, interval: Interval, n: int, *, min_syllable: float = 0.055
) -> list[Interval]:
    """区間を n 音節に分割する.

    音節数が既知なので「自由に核を検出する」のではなく、**強度の谷を
    ちょうど n-1 本選ぶ**問題として解く（動的計画法）．連続発話では
    共鳴音どうしの境界で谷が浅くなり自由検出は破綻するが、本数を
    固定すれば安定する．
    """
    a, b = interval
    if n <= 1 or b - a < min_syllable * 2:
        return [(a, b)]
    t, v = rec.intensity_in(a, b)
    if len(t) < n + 2:
        edges = np.linspace(a, b, n + 1)
        return list(zip(edges[:-1], edges[1:]))

    # 無声区間は境界として有利にする（谷として扱う）
    m = (rec.itime >= a) & (rec.itime <= b)
    voiced = rec.voiced_at_itime[m]
    score = v - 8.0 * (1.0 - voiced)  # 低いほど境界にふさわしい

    step = max(1, int(round(min_syllable / rec.time_step)))
    m = len(t)
    INF = float("inf")
    # dp[k][i] = 先頭から k 本の境界を打ち、最後の境界が i のときの最小コスト
    dp = np.full((n, m), INF)
    bk = np.full((n, m), -1, dtype=int)
    for i in range(step, m - step):
        dp[1][i] = score[i]
    for k in range(2, n):
        for i in range(k * step, m - step):
            j0, j1 = (k - 1) * step, i - step + 1
            if j1 <= j0:
                continue
            seg = dp[k - 1][j0:j1]
            if not np.isfinite(seg).any():
                continue
            jrel = int(np.nanargmin(np.where(np.isfinite(seg), seg, np.inf)))
            dp[k][i] = seg[jrel] + score[i]
            bk[k][i] = j0 + jrel
    last = dp[n - 1][: m - step]
    if not np.isfinite(last).any():
        edges = np.linspace(a, b, n + 1)
        return list(zip(edges[:-1], edges[1:]))
    i = int(np.nanargmin(np.where(np.isfinite(last), last, np.inf)))
    cuts = []
    k = n - 1
    while k >= 1 and i >= 0:
        cuts.append(t[i])
        i = bk[k][i]
        k -= 1
    cuts = sorted(cuts)
    edges = [a, *cuts, b]
    return list(zip(edges[:-1], edges[1:]))


# ---------------------------------------------------------------------------
# 5. 測定
# ---------------------------------------------------------------------------


def _semitones(f: np.ndarray, ref: float) -> np.ndarray:
    return 12.0 * np.log2(np.maximum(f, 1e-6) / ref)


@dataclass
class SyllableMeasurement:
    index: int
    label: str
    start: float
    end: float
    duration: float
    n_f0: int
    voiced_frac: float
    f0_mean: float
    f0_start: float
    f0_end: float
    f0_min: float
    f0_max: float
    slope_st_per_s: float
    excursion_st: float
    level_st: float           # 語全体の中央値からの隔たり（半音）
    auto_label: str

    def as_row(self) -> dict:
        return {
            "syl_index": self.index + 1,
            "syllable": self.label,
            "start": round(self.start, 4),
            "end": round(self.end, 4),
            "dur_ms": round(self.duration * 1000, 1),
            "voiced": round(self.voiced_frac, 3),
            "n_f0": self.n_f0,
            "f0_mean": round(self.f0_mean, 1) if math.isfinite(self.f0_mean) else "",
            "f0_start": round(self.f0_start, 1) if math.isfinite(self.f0_start) else "",
            "f0_end": round(self.f0_end, 1) if math.isfinite(self.f0_end) else "",
            "slope_st_s": round(self.slope_st_per_s, 2) if math.isfinite(self.slope_st_per_s) else "",
            "excursion_st": round(self.excursion_st, 2) if math.isfinite(self.excursion_st) else "",
            "level_st": round(self.level_st, 2) if math.isfinite(self.level_st) else "",
            "auto": self.auto_label,
        }


def measure_syllables(
    rec: Recording,
    intervals: Sequence[Interval],
    labels: Sequence[str],
    *,
    reference_f0: float,
    fall_threshold_st: float = 2.5,
    level_threshold_st: float = 1.5,
    edge_trim: float = 0.15,
) -> list[SyllableMeasurement]:
    """音節区間ごとに f0 と持続時間を測る.

    ``auto_label`` は目安であって判定ではない．しきい値を変えれば変わるし、
    ``level_st`` と ``excursion_st`` の生値の方が分析には向く．
    """
    per: list[SyllableMeasurement] = []
    means = []
    raw = []
    for (a, b), lab in zip(intervals, labels):
        d = b - a
        ta, tb = a + d * edge_trim, b - d * edge_trim
        t, f = rec.f0_in(ta, tb)
        if len(f) < 3:
            t, f = rec.f0_in(a, b)
        raw.append((a, b, lab, t, f))
        if len(f):
            means.append(np.median(f))
    word_ref = float(np.median(means)) if means else reference_f0

    for i, (a, b, lab, t, f) in enumerate(raw):
        d = b - a
        vf = rec.voiced_fraction(a, b)
        if len(f) >= 3:
            st = _semitones(f, word_ref)
            k = max(1, len(f) // 5)
            f_start, f_end = float(np.median(f[:k])), float(np.median(f[-k:]))
            A = np.c_[np.ones(len(t)), t - t[0]]
            coef, *_ = np.linalg.lstsq(A, st, rcond=None)
            slope = float(coef[1])
            exc = float(_semitones(np.array([f_end]), f_start)[0])
            level = float(np.median(st))
            fmean, fmin, fmax = float(np.mean(f)), float(f.min()), float(f.max())
        else:
            f_start = f_end = fmean = fmin = fmax = float("nan")
            slope = exc = level = float("nan")

        if not math.isfinite(exc):
            auto = "?"
        elif exc <= -fall_threshold_st:
            auto = "F"
        elif exc >= fall_threshold_st:
            auto = "R"
        elif level >= level_threshold_st:
            auto = "H"
        elif level <= -level_threshold_st:
            auto = "L"
        else:
            auto = "H" if level >= 0 else "L"

        per.append(
            SyllableMeasurement(
                index=i,
                label=lab,
                start=a,
                end=b,
                duration=d,
                n_f0=len(f),
                voiced_frac=vf,
                f0_mean=fmean,
                f0_start=f_start,
                f0_end=f_end,
                f0_min=fmin,
                f0_max=fmax,
                slope_st_per_s=slope,
                excursion_st=exc,
                level_st=level,
                auto_label=auto,
            )
        )
    return per


# ---------------------------------------------------------------------------
# 6. TextGrid 出力
# ---------------------------------------------------------------------------


def write_textgrid(
    path: str | Path,
    duration: float,
    tiers: dict[str, Sequence[tuple[float, float, str]]],
):
    """Praat の TextGrid を書き出す（手修正用）."""
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0",
        f"xmax = {duration}",
        "tiers? <exists>",
        f"size = {len(tiers)}",
        "item []:",
    ]
    for ti, (name, ivals) in enumerate(tiers.items(), 1):
        iv = sorted(ivals)
        filled: list[tuple[float, float, str]] = []
        prev = 0.0
        for a, b, lab in iv:
            if a > prev + 1e-6:
                filled.append((prev, a, ""))
            filled.append((a, b, lab))
            prev = b
        if prev < duration:
            filled.append((prev, duration, ""))
        lines += [
            f"    item [{ti}]:",
            '        class = "IntervalTier"',
            f'        name = "{name}"',
            "        xmin = 0",
            f"        xmax = {duration}",
            f"        intervals: size = {len(filled)}",
        ]
        for k, (a, b, lab) in enumerate(filled, 1):
            lines += [
                f"        intervals [{k}]:",
                f"            xmin = {a}",
                f"            xmax = {b}",
                f'            text = "{lab}"',
            ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# まとめ
# ---------------------------------------------------------------------------


@dataclass
class TokenResult:
    stimulus_index: int
    word: Word
    utterance: Interval
    target: Interval
    carrier: Interval
    carrier_score: float
    syllables: list[SyllableMeasurement]
    warnings: list[str] = field(default_factory=list)


def analyse(
    rec: Recording,
    words: Sequence[Word],
    *,
    carrier_mode: str = "suffix",
    threshold_frac: float = 0.40,
    min_silence: float = 0.35,
    progress=None,
):
    """録音全体を刺激列に対応づけて測定する.

    ``carrier_mode``
        ``"suffix"``  目標語のあとにだけキャリアが付く（``X kino danktai``）
        ``"frame"``   目標語を前後から挟む（``kino X danktai``）
    """
    utts = segment_utterances(rec, threshold_frac=threshold_frac, min_silence=min_silence)
    align = align_utterances(utts, [w.n_syllables for w in words])

    if carrier_mode == "frame":
        carrier, bounds = FrameCarrier.build(
            rec, align.intervals, [w.n_syllables for w in words]
        )
        spans = [(t0, t1, sc) for t0, t1, sc in bounds]
        scores = np.array([sc for _a, _b, sc in bounds])
    else:
        carrier = CarrierModel.build(rec, align.intervals)
        spans = []
        for iv in align.intervals:
            c_on, sc = carrier.onset(rec, iv)
            spans.append((iv[0], c_on, sc))
        scores = np.array([sc for _a, _b, sc in spans])

    all_f0 = rec.f0[np.isfinite(rec.f0)]
    ref = float(np.median(all_f0)) if len(all_f0) else 120.0
    lowq = float(np.percentile(scores, 2)) if len(scores) else -1e9

    results: list[TokenResult] = []
    for i, (w, iv, (t0, t1, sc)) in enumerate(zip(words, align.intervals, spans)):
        target = (t0, t1)
        warns: list[str] = []
        if target[1] - target[0] < 0.09 * w.n_syllables:
            warns.append("目標語区間が短すぎる（キャリア検出が外れた可能性）")
        if sc < lowq:
            warns.append("キャリア照合スコアが低い")
        sylv = split_syllables(rec, target, w.n_syllables)
        meas = measure_syllables(rec, sylv, [s.spell for s in w.syllables], reference_f0=ref)
        if any(m.voiced_frac < 0.35 for m in meas):
            warns.append("無声区間の多い音節がある")
        results.append(
            TokenResult(
                stimulus_index=i,
                word=w,
                utterance=iv,
                target=target,
                carrier=(t1, iv[1]),
                carrier_score=sc,
                syllables=meas,
                warnings=warns,
            )
        )
        if progress and (i + 1) % 25 == 0:
            progress(i + 1, len(words))
    return results, align, carrier
