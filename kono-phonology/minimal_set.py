"""gogaku/coining.tex「ミニマルセット」節の検証実装。

- 平衡化モデル（色彩割り当て・モデル化・平衡化・良配列判定）
- 良さの勾配（輸送量 D・反復度 OCP・分散度 Disp）
- 方向性平衡化（語根制御型・優勢型）と量子化
- tex 中の例（melon, kakin, kikikiki, kanomel→kanomol, meloma→molama）の再現テスト
- v5 辞書のミニマルセット語のスコア分布

用法: python3 minimal_set.py [--dict]
"""

import itertools
import json
import math
import sys

# ---- 割り当て（coining.tex subsec:min-assign） ----

VOWELS = {"o": (1, 0), "a": (1, 1), "e": (0, -1), "i": (0, 0),"u": (1/2, 1/2)}
# theta: (alpha透過, beta透過)
CONSONANTS = {
    "k": (True, False), "f": (True, False), "h": (False, True),
    "s": (True, True), "c": (True, True), "l": (True, True),
    "m": (False, True), "t": (False, True), "n": (False, True),
}

# A^{-1}: (alpha,beta,gamma=0) -> (R,G,B)
def realizable(ab):
    a, b = ab
    # A = 1/2 [[1,1,0],[1,1,-2],[1,-1,0]], gamma=0
    # 逆変換: R = a + g = a, G = a - g = a (g=0だが正しくは逆行列で)
    # A^{-1} を直接計算: R=alpha+gamma, G=alpha-gamma, B=alpha-beta （検算: A(R,G,B)/…）
    R = a 
    G = a
    B = a - b
    return all(-1e-9 <= x <= 1 + 1e-9 for x in (R, G, B))


# ---- モデル（def:min-model） ----

def build_model(word):
    """word -> (vowel_colors, wall_thetas) 形式。
    walls[i] は vowels[i-1] と vowels[i] の間（両端は背景との間）。
    戻り値: (vowels: list[(a,b)], walls: list[(bool,bool)]) len(walls)=len(vowels)+1
    """
    # トークン化（1文字音素のみ：ミニマルセット）
    toks = list(word)
    vcolors, walls = [], []
    cur = []  # 現在の子音クラスタ
    for t in toks:
        if t in VOWELS:
            th = (all(CONSONANTS[c][0] for c in cur), all(CONSONANTS[c][1] for c in cur))
            walls.append(th)
            vcolors.append(VOWELS[t])
            cur = []
        elif t in CONSONANTS:
            cur.append(t)
        else:
            raise ValueError(f"ミニマルセット外の文字: {t!r} in {word!r}")
    walls.append((all(CONSONANTS[c][0] for c in cur), all(CONSONANTS[c][1] for c in cur)))
    return vcolors, walls


# ---- 平衡化（def:min-equilibration） ----

def equilibrate(vcolors, walls, bg):
    """背景 bg のもとで平衡化。戻り値 (new_colors, left_color, right_color)."""
    n = len(vcolors)
    new = [list(v) for v in vcolors]
    seen = [bg[0], bg[1]]  # 左・右から見た色は成分別に計算
    left = [None, None]
    right = [None, None]
    for j in (0, 1):
        # 遮断壁で区間分割。区間は母音インデックスの並び。壁 i は v[i-1]|v[i] 間。
        segs = []
        start = 0
        for i in range(1, n):
            if not walls[i][j]:
                segs.append((start, i))
                start = i
        segs.append((start, n))
        # 背景に接続するか: 左端区間は walls[0][j] が透過なら背景に接続、右端も同様
        for (s, e) in segs:
            touch_left = (s == 0 and walls[0][j])
            touch_right = (e == n and walls[n][j])
            vals = [vcolors[i][j] for i in range(s, e)]
            if touch_left or touch_right:
                q = bg[j] + sum(v - bg[j] for v in vals)
                for i in range(s, e):
                    new[i][j] = bg[j]
                if touch_left:
                    left[j] = q
                if touch_right:
                    right[j] = q
            elif e > s:
                m = sum(vals) / len(vals)
                for i in range(s, e):
                    new[i][j] = m
        if left[j] is None:
            left[j] = bg[j]
        if right[j] is None:
            right[j] = bg[j]
    return [tuple(v) for v in new], tuple(left), tuple(right)


def wellformed_under(word, bg):
    vc, walls = build_model(word)
    new, L, R = equilibrate(vc, walls, bg)
    if not vc:
        return True
    same = all(abs(new[i][0] - new[0][0]) < 1e-9 and abs(new[i][1] - new[0][1]) < 1e-9
               for i in range(len(new)))
    return same # and realizable(new[0]) #and realizable(L) and realizable(R)


BG_CANDIDATES = [(a, b) for a in (0, 0.25, 0.5, 0.75, 1) for b in (-1, -0.5, 0, 0.5, 1)
                 if realizable((a, b))] + list(VOWELS.values())


def wellformed(word):
    """良配列か（背景の存在量化はグリッド＋母音色で近似）。成立させる背景の集合も返す。"""
    goods = [bg for bg in BG_CANDIDATES if wellformed_under(word, bg)]
    return (len(goods) > 0), goods


# ---- 勾配（subsec:min-gradient） ----

def transport(word, bg):
    vc, walls = build_model(word)
    new, _, _ = equilibrate(vc, walls, bg)
    return sum(abs(a0 - a1) + abs(b0 - b1) for (a0, b0), (a1, b1) in zip(vc, new))

def ocp(word):
    vc, _ = build_model(word)
    return sum(1 for i in range(len(vc) - 1) if vc[i] == vc[i + 1])

def dispersion(word):
    vc, _ = build_model(word)
    if len(vc) < 2:
        return None
    return min(math.dist(p, q) for p, q in itertools.combinations(vc, 2))


# ---- 方向性平衡化（sec:zouko-affix） ----

def directional(word, sources, root_range):
    """sources: 色源となる母音インデックス集合。root_range: 語根側の母音 index 範囲（タイブレーク用）。
    戻り値: 量子化後の母音文字列（母音のみ）。"""
    vc, walls = build_model(word)
    n = len(vc)
    new = [list(v) for v in vc]
    changed = [[False, False] for _ in range(n)]
    for j in (0, 1):
        segs = []
        start = 0
        for i in range(1, n):
            if not walls[i][j]:
                segs.append((start, i))
                start = i
        segs.append((start, n))
        for (s, e) in segs:
            srcs = [i for i in range(s, e) if i in sources]
            if not srcs:
                continue
            for i in range(s, e):
                if i in sources:
                    continue
                dmin = min(abs(i - k) for k in srcs)
                cands = [k for k in srcs if abs(i - k) == dmin]
                # 等距離は語根側優先
                k = min(cands, key=lambda k: 0 if k in root_range else 1)
                if new[i][j] != vc[k][j]:
                    changed[i][j] = True
                new[i][j] = vc[k][j]
    # 量子化
    out = []
    for i in range(n):
        if i in sources:
            out.append(_vowel_of(vc[i]))
            continue
        x = tuple(new[i])
        dists = {v: math.dist(x, p) for v, p in VOWELS.items()}
        dmin = min(dists.values())
        cands = [v for v, d in dists.items() if abs(d - dmin) < 1e-9]
        if len(cands) > 1:
            # 色源に書き換えられた成分が一致するものを優先
            keep = [v for v in cands
                    if all(not changed[i][j] or abs(VOWELS[v][j] - new[i][j]) < 1e-9 for j in (0, 1))]
            if keep:
                cands = keep
        if len(cands) > 1:
            cands.sort(key=lambda v: math.dist(VOWELS[v], vc[i]))
        out.append(cands[0])
    return out

def _vowel_of(color):
    for v, p in VOWELS.items():
        if p == tuple(color):
            return v
    return "?"

def harmonized(word, n_root_vowels, dominant_suffix=False):
    """語根+接辞結合済みの word に対し調和形（全体の綴り）を返す。"""
    vc, _ = build_model(word)
    n = len(vc)
    root = set(range(n_root_vowels))
    sources = root if not dominant_suffix else set(range(n_root_vowels, n))
    newv = directional(word, sources, root)
    # 母音を差し替えて綴りを再構成
    out, vi = [], 0
    for ch in word:
        if ch in VOWELS:
            out.append(newv[vi]); vi += 1
        else:
            out.append(ch)
    return "".join(out)


# ---- テスト（tex の例の再現） ----

def run_tests():
    ok = True
    def check(name, cond, detail=""):
        nonlocal ok
        print(f"[{'OK' if cond else 'NG'}] {name}" + (f"  {detail}" if detail else ""))
        ok = ok and cond

    # melon: 背景(1,0)で良配列、左から見た色(0,-1)、右(0,0)
    vc, walls = build_model("melon")
    new, L, R = equilibrate(vc, walls, (1, 0))
    check("melon 良配列 (bg=(1,0))", wellformed_under("melon", (1, 0)))
    check("melon 左から見た色 = (0,-1)", L == (0, -1), f"got {L}")
    # tex の例は (0,0) とするが、定義 def:min-equilibration に従うと
    # n は α を遮断するため右背景区間に母音が無く、和が空で q = φ(B) = (1,0) になる。
    # tex 側の例の誤りと思われる（coining.tex 要修正）。
    check("melon 右から見た色 = (1,0)（tex の (0,0) は定義と不整合）", R == (1, 0), f"got {R}")

    # kakin: どの背景でも良配列でない
    wf, _ = wellformed("kakin")
    check("kakin は良配列でない", not wf)

    # kikikiki: 良配列かつ輸送量 0
    wf, goods = wellformed("kikikiki")
    check("kikikiki は良配列", wf)
    if goods:
        check("kikikiki 輸送量 = 0", transport("kikikiki", goods[0]) == 0)
    check("kikikiki OCP = 3", ocp("kikikiki") == 3, f"got {ocp('kikikiki')}")

    # melon の輸送量 > 0
    check("melon 輸送量 > 0 (bg=(1,0))", transport("melon", (1, 0)) > 0,
          f"D={transport('melon',(1,0))}")

    # 語根制御型: kano + mel -> kanomol
    h = harmonized("kanomel", 2, dominant_suffix=False)
    check("kanomel（語根制御）→ kanomol", h == "kanomol", f"got {h}")

    # 優勢型: melo + ma -> molama
    h = harmonized("meloma", 2, dominant_suffix=True)
    check("meloma（優勢接辞）→ molama", h == "molama", f"got {h}")

    # === debug ===
    res = wellformed_under("konomeno", (1,0))
    print(res)

    print("\n" + ("全テスト通過" if ok else "失敗あり"))
    return ok


# ---- 辞書スキャン ----

DICT_PATH = "/Users/kohigen/Documents/kono-main/kono-dictionary-editor/src/data/konomeno-v5.json"
MINSET = set(VOWELS) | set(CONSONANTS)

def scan_dict():
    words = json.load(open(DICT_PATH))["words"]
    entries = sorted({w["entry"] for w in words
                      if w and w.get("entry") and set(w["entry"]) <= MINSET})
    print(f"ミニマルセット語: {len(entries)} 語\n")
    rows = []
    for e in entries:
        wf, goods = wellformed(e)
        if wf:
            D = max(transport(e, bg) for bg in goods)
        else:
            D = None
        rows.append((e, wf, D, ocp(e), dispersion(e)))
    n_wf = sum(1 for r in rows if r[1])
    print(f"良配列: {n_wf}/{len(rows)}\n")
    print(f"{'語':<12}{'良配列':<6}{'D(max)':<8}{'OCP':<5}{'Disp'}")
    for e, wf, D, o, disp in rows:
        print(f"{e:<12}{'○' if wf else '×':<6}"
              f"{D if D is not None else '-':<8}{o:<5}"
              f"{f'{disp:.2f}' if disp is not None else '-'}")


if __name__ == "__main__":
    ok = run_tests()
    if "--dict" in sys.argv:
        print()
        scan_dict()
    sys.exit(0 if ok else 1)
