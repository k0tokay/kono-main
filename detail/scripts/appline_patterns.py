from dataclasses import dataclass
from itertools import combinations, product


def appline_list(max_length: int = 15):
    """
    result_ordered[i] には
        ・非ブランクトークンの個数 == i
        ・ブランク数が少ない順（0,1,2,...）
    で重複なし・挿入順保持の語形を並べる。
    """
    # Ordered-Set としての buckets[non_blank_len]
    buckets = [dict() for _ in range(max_length + 1)]

    def add(form: str):
        """重複を除きつつ buckets へ追加"""
        nblen = len(form) - form.count("_")  # 非ブランク長
        if 0 <= nblen <= max_length and form not in buckets[nblen]:
            buckets[nblen][form] = None
            return True
        return False

    # ---------- レイヤー 0（省略なし） ----------
    for n in range(max_length + 1):
        if n % 2 == 1:
            add("t" + "Rt" * (n // 2))  # tRtRt...
    for n in range(max_length + 1):
        if n == 1:
            add("R")  # t
        if n >= 2:
            add("tR" + "t" * (n - 2))  # tRtt...

    # ---------- レイヤー 1 以降 ----------
    prev_layer = [list(d.keys()) for d in buckets]
    for _ in range(1, max_length):  # ブランク数 1,2,...
        next_layer = [[] for _ in range(max_length + 1)]
        for forms in prev_layer:
            for s in forms:
                for i, ch in enumerate(s):
                    if ch == "t":
                        new_s = s[:i] + "_" + s[i + 1 :]
                        if add(new_s):
                            nblen = len(new_s) - new_s.count("_")
                            next_layer[nblen].append(new_s)
        if all(not layer for layer in next_layer):
            break  # これ以上増えない
        prev_layer = next_layer

    # ---------- dict → list ----------
    result_ordered = [list(d.keys()) for d in buckets]

    # _なしで見たときに一意になるように
    result_unique = []
    for length, patterns in enumerate(result_ordered):
        seen = set()
        unique_patterns = []
        for pat in patterns:
            key = pat.replace("_", "")  # _を無視した形
            if key not in seen:
                seen.add(key)
                unique_patterns.append(pat)
        result_unique.append(unique_patterns)
    return result_ordered, result_unique


# ============================================================
# 体系S：パターン照合と善意的解釈
# ============================================================
#
# formal-grammar.tex §体系S の規則をそのまま実装する。ただし，語彙は
# 「関係は大文字トークン，個体は小文字トークン」という単純な辞書として
# 扱い，{x | Px} のような内包的な項（名詞化・関数適用）は考えない。
# そのため sort(t) の計算も「個体定数の宣言済みソート，それ以外は
# alkono（⊤）」の2ケースだけに単純化してある。

TOP = "alkono"  # 万物概念。宣言されていない項の統語ソートはここに落ちる。


@dataclass
class Relation:
    arity: int
    dom: tuple  # 長さ arity。各引数位置の統語ソート（概念名）


class Lexicon:
    """関係は大文字トークン，個体は小文字トークンとして登録する語彙。"""

    def __init__(self):
        self._parents = {TOP: ()}  # 概念名 -> 直接の上位概念（⪯ の Hasse 図）
        self.individuals = {}  # 個体名 -> 統語ソート（概念名）
        self.relations = {}  # 関係名 -> Relation
        self._implications = {}  # 同じ引数列についての語彙的含意（強い関係 -> 弱い関係）

    def add_concept(self, name: str, parents=(TOP,)):
        self._parents[name] = tuple(parents)

    def add_individual(self, name: str, sort: str = TOP):
        self._parents.setdefault(sort, (TOP,))
        self.individuals[name] = sort

    def add_relation(self, name: str, dom: tuple = ()):
        for s in dom:
            self._parents.setdefault(s, (TOP,))
        self.relations[name] = Relation(arity=len(dom), dom=tuple(dom))

    def add_implication(self, stronger: str, weaker: str):
        """同じアリティの述語間の含意を登録する。domの一致だけでは推論しない。"""
        if self.relations[stronger].arity != self.relations[weaker].arity:
            raise ValueError("implication requires equal arities")
        self._implications.setdefault(stronger, set()).add(weaker)

    def atom_entails(self, premise, conclusion) -> bool:
        """正規化済み原子の含意。語彙含意と各引数のソートへの射影を使う。"""
        rel, args = premise
        target, target_args = conclusion
        reachable = set()
        stack = [rel]
        while stack:
            name = stack.pop()
            if name in reachable:
                continue
            reachable.add(name)
            stack.extend(self._implications.get(name, ()))
        if args == target_args and target in reachable:
            return True
        if len(target_args) != 1 or target not in self._parents:
            return False
        # 概念述語の包含と、関係の引数ソートから従う1項述語。
        if len(args) == 1 and args == target_args and rel in self._parents:
            if self.leq(rel, target):
                return True
        for name in reachable:
            relation = self.relations.get(name)
            if relation is not None:
                for arg, sort in zip(args, relation.dom):
                    if (arg,) == target_args and self.leq(sort, target):
                        return True
        return False

    def leq(self, a: str, b: str) -> bool:
        """a ⪯ b：概念のHasse図（親=直接の上位概念）上の到達可能性。"""
        if a == b:
            return True
        seen = set()
        stack = [a]
        while stack:
            c = stack.pop()
            for p in self._parents.get(c, ()):
                if p == b:
                    return True
                if p not in seen:
                    seen.add(p)
                    stack.append(p)
        return False

    def sort_of(self, name: str) -> str:
        """統語ソート sort(t)。個体定数以外（関数適用・名詞化）は非対応。"""
        return self.individuals.get(name, TOP)


def _split_suffix(token: str):
    """接尾辞 ``:I``（個体として解釈）／``:R``（関係として解釈）を分離する。"""
    if token.endswith(":I"):
        return token[:-2], "I"
    if token.endswith(":R"):
        return token[:-2], "R"
    return token, None


def match_categories(lex: Lexicon, token: str) -> tuple:
    """m(e_i)：トークンの照合候補（'t' と/または 'R'）。"""
    name, suffix = _split_suffix(token)
    if suffix == "I":
        return ("t",)
    if suffix == "R":
        return ("R",)
    if name in lex.individuals:
        return ("t",)
    if name in lex.relations:
        return ("R",)
    return ("t", "R")  # 辞書に無いトークン（複合表現・未知語）


def _alternating_pattern(hat, r_positions) -> str:
    """交互型のパターンを直接組み立てる。関係はブランクにならないので，
    隣接するR同士（および文頭・文末）の間に高々1つ置けるtが実際にあるか
    どうかだけで，ブランクの位置は一意に決まる（自由度なし）。
    """
    parts = []
    prev = -1
    for rp in r_positions:
        gap = hat[prev + 1 : rp]
        parts.append(gap[0] if gap else "_")
        parts.append("R")
        prev = rp
    gap = hat[prev + 1 :]
    parts.append(gap[0] if gap else "_")
    return "".join(parts)


def _multiarg_patterns(r_pos: int, arity: int, n: int):
    """多引数型のブランク配置を列挙する。Rの直前に置ける個体は高々1つで
    hat から一意に決まるため，自由度はRの後ろの post_slots 個のスロット
    に，実際に書かれた m_post 個のtをどう配置するかだけに限られる
    （$\\binom{\\mathrm{post\\_slots}}{m_{\\mathrm{post}}}$ 通り）。
    """
    if arity == 0:
        return ["R"] if n == 1 else []
    slot1 = "t" if r_pos == 1 else "_"
    post_slots = arity - 1
    m_post = n - r_pos - 1
    if m_post > post_slots:
        return []
    variants = []
    for chosen in combinations(range(post_slots), m_post):
        chosen_set = set(chosen)
        body = "".join("t" if i in chosen_set else "_" for i in range(post_slots))
        variants.append(slot1 + "R" + body)
    return variants


def _candidate_patterns(lex: Lexicon, tokens):
    """文 tokens に対して妥当な (パターン, 優先度) の組を列挙する。

    $\\mathcal P$ を総当たりするのではなく，各トークンの実際の資格
    （と，既知なら関係の実際のアリティ）から直接パターンを組み立てる：
    関係はブランクにならない（省略されるのはtの位置だけ）ので，交互型は
    アリティもブランクの置き方も一意に決まり，多引数型もRの前に置ける
    個体が高々1つという制約のおかげで，自由度はRの後ろのどこを省略する
    かという（アリティで抑えられた）小さな組合せだけになる。これにより
    無関係な全長・全アリティを検索する必要がなくなる。
    """
    n = len(tokens)
    categories = [match_categories(lex, tok) for tok in tokens]
    results = []
    for hat in product(*categories):
        r_positions = [i for i, ch in enumerate(hat) if ch == "R"]
        r_count = len(r_positions)

        if r_count == 0:
            if n == 1:
                results.append(("t", (0, 0)))
            continue

        if r_count == 1:
            r_pos = r_positions[0]
            if r_pos > 1:
                continue  # 多引数型はRの前に個体を高々1つしか置けない
            rel_name, _ = _split_suffix(tokens[r_pos])
            rel = lex.relations.get(rel_name)
            overt_t = n - 1
            arity = rel.arity if rel is not None else overt_t
            needed_blanks = arity - overt_t
            if needed_blanks < 0:
                continue
            variants = _multiarg_patterns(r_pos, arity, n)
        else:
            if any(hat[i] == "t" and hat[i + 1] == "t" for i in range(n - 1)):
                continue  # 交互型はRを挟まずにtが連続できない
            if any(
                (rel := lex.relations.get(_split_suffix(tokens[i])[0])) is not None
                and rel.arity != 2
                for i in r_positions
            ):
                continue
            needed_blanks = 0  # 交互型はブランクの置き方に自由度がない
            variants = [_alternating_pattern(hat, r_positions)]

        for pos, p in enumerate(variants):
            results.append((p, (needed_blanks, pos)))
    return results


def _align(p: str, tokens):
    """p の各文字位置に ('token', j) または ('blank', None) を対応させる。
    非ブランク文字は左から順に tokens と一対一に対応する。
    """
    seq = []
    j = 0
    for ch in p:
        if ch == "_":
            seq.append(("blank", None))
        else:
            seq.append(("token", j))
            j += 1
    return seq


def _touch(delta: tuple, name: str) -> tuple:
    """指示対象 name をΔの先頭に移動する（未登場なら挿入）。"""
    return (name,) + tuple(x for x in delta if x != name)


def _enumerate_resolutions(p: str, tokens, delta0: tuple):
    """線形文 p を左から走査し，ブランクごとにΔからの参照先を選ぶ。
    戻り値は (referents, rec_positions, delta_after) のリスト。
    referents は p の各文字位置に対応する指示対象（R位置は None）。
    rec_positions は各ブランクをΔ_iの何番目（0=最新）に解決したかの列。
    """
    seq = _align(p, tokens)
    results = []

    def rec(idx, delta, referents, rec_positions):
        if idx == len(p):
            results.append((tuple(referents), tuple(rec_positions), delta))
            return
        ch = p[idx]
        if ch == "R":
            _, j = seq[idx]
            rec(idx + 1, delta, referents + [None], rec_positions)
            return
        kind, j = seq[idx]
        if kind == "token":
            name, _ = _split_suffix(tokens[j])
            rec(idx + 1, _touch(delta, name), referents + [name], rec_positions)
        else:  # ブランク
            for pos, cand in enumerate(delta):
                rec(
                    idx + 1,
                    _touch(delta, cand),
                    referents + [cand],
                    rec_positions + [pos],
                )

    rec(0, tuple(delta0), [], [])
    return results


def _atom_templates(p: str):
    """パターン p から (Rの位置, 引数の位置のタプル) の列を返す。
    r_count==0（"t" 単体）なら空リスト，r_count==1（多引数型）なら要素1つ，
    r_count>=2（交互型）ならr_count個の隣接ペア。
    """
    r_positions = [i for i, ch in enumerate(p) if ch == "R"]
    t_positions = [i for i, ch in enumerate(p) if ch != "R"]
    if not r_positions:
        return []
    if len(r_positions) == 1:
        return [(r_positions[0], tuple(t_positions))]
    return [
        (r_positions[k], (t_positions[k], t_positions[k + 1]))
        for k in range(len(r_positions))
    ]


def _tau_options(templates):
    """各原子の転置候補：2項ならτ∈{0,1}，それ以外は転置の自由度なし。"""
    return [(0, 1) if len(arg_positions) == 2 else (0,) for _, arg_positions in templates]


@dataclass
class Analysis:
    """善意的解釈における解析 α = ⟨p, τ, g⟩ とその読み・違反ベクトル。"""

    pattern: str
    pattern_index: tuple  # (必要ブランク数, 同ブランク数内での優先順位)
    tau: tuple
    atoms: list  # [(rel_name, args, transposed, blank_flags), ...]
    rec_positions: tuple
    delta_after: tuple
    v: tuple

    def reading_str(self) -> str:
        if not self.atoms:
            return "(空)"
        parts = []
        for rel, args, transposed, _ in self.atoms:
            name = f"{rel}^T" if transposed else rel
            parts.append(f"{name}({', '.join(args)})")
        return " ∧ ".join(parts)


def _dom_order(lex: Lexicon, rel_name: str, arity: int, transposed: bool) -> tuple:
    rel = lex.relations.get(rel_name)
    dom = rel.dom if rel is not None else (TOP,) * arity
    if transposed and len(dom) == 2:
        dom = (dom[1], dom[0])
    return dom


def _h1_sort_ok(lex: Lexicon, atoms) -> bool:
    """ハードフィルタ(H1)：ソート整合。"""
    for rel_name, args, transposed, _ in atoms:
        dom = _dom_order(lex, rel_name, len(args), transposed)
        if len(args) != len(dom):
            return False
        for a, d in zip(args, dom):
            if not lex.leq(lex.sort_of(a), d):
                return False
    return True


def _h2_coargument_ok(atoms) -> bool:
    """ハードフィルタ(H2)：共項排除（ブランクは同一原子内の他の引数と同じ
    指示対象に解決されない）。"""
    for _, args, _, blank_flags in atoms:
        for i in range(len(args)):
            if not blank_flags[i]:
                continue
            for j in range(len(args)):
                if i != j and args[i] == args[j]:
                    return False
    return True


def _atom_key(atom):
    """転置を反映した原子。同じ関係・同じ引数列を同一視する。"""
    rel_name, args, transposed, *_ = atom
    args = tuple(args)
    return rel_name, tuple(reversed(args)) if transposed else args


def _v_red(atoms, lex: Lexicon | None = None) -> int:
    """情報を保って削除できる連言肢の最大数（本文の v_red）。

    語彙含意がなければ「総数 - 異なる原子数」で、p∧pは1、p∧p∧pは2。
    lexがあれば、登録された述語間の含意・ソート射影も使う。
    この実装の含意は1原子から1原子への規則なので、含意の同値類のうち
    他の類から従わないものを1個ずつ残せば最小基底になる。
    複数の前提を同時に要する一般の論理的含意は扱わない。
    """
    keys = list(dict.fromkeys(_atom_key(atom) for atom in atoms))
    if lex is None or not lex._implications:
        # 2項以上の原子だけならソート射影先の1項原子がない。
        if lex is None or all(len(args) != 1 for _, args in keys):
            return len(atoms) - len(keys)
    entails = [[lex.atom_entails(a, b) for b in keys] for a in keys]
    # 推移閉包。循環する同値述語も1個だけ残す。
    for k in range(len(keys)):
        for i in range(len(keys)):
            if entails[i][k]:
                for j in range(len(keys)):
                    entails[i][j] = entails[i][j] or entails[k][j]
    retained = 0
    for i in range(len(keys)):
        equivalent_earlier = any(entails[i][j] and entails[j][i] for j in range(i))
        strictly_implied = any(entails[j][i] and not entails[i][j] for j in range(len(keys)))
        if not equivalent_earlier and not strictly_implied:
            retained += 1
    return len(atoms) - retained


def _v_tau(lex: Lexicon, atoms) -> int:
    """自由転置数 v_tau：ソートが強制しないのにτ=1を選んだ個数。"""
    count = 0
    for rel_name, args, transposed, _ in atoms:
        if len(args) != 2 or not transposed:
            continue
        dom0 = _dom_order(lex, rel_name, 2, False)
        if lex.leq(lex.sort_of(args[0]), dom0[0]) and lex.leq(lex.sort_of(args[1]), dom0[1]):
            count += 1
    return count


def _atom_tau_options(lex: Lexicon, rel_name: str, args: tuple):
    """この原子（2項）についてH1を満たすτを，(τ, 自由選択かどうか) の形で
    τ=0優先の順に返す（自由＝両方向ともソート整合，の意）。
    """
    valid = [
        tau
        for tau in (0, 1)
        if all(
            lex.leq(lex.sort_of(a), d)
            for a, d in zip(args, _dom_order(lex, rel_name, 2, bool(tau)))
        )
    ]
    free = len(valid) == 2
    return [(tau, free) for tau in valid]


def _search_chain(lex: Lexicon, p: str, tokens, delta0: tuple):
    """交互型（原子数>=2）専用の善意的解釈探索。

    原子を左から確定させながら τ=0優先・Δ先頭優先の順で試すバックトラック
    探索で，v_red・v_tauは単調非減少（原子を追加しても減ることはない）と
    いう性質を使って枝刈りする。全列挙探索
    だと R^n のようなブランクだらけの文でΔ^ブランク数×2^原子数に爆発して
    いたが，ここでは「今見つかっている最良解より既に悪い」枝を原子1つ
    処理するごとに切り捨てるので，実際に探索される分岐は大きく減る。
    v_redは最小基底からの削除数を各接頭辞で再計算する。新しい強い原子が
    既存の複数原子を含意する場合も、単なる重複の加算ではなくここで反映する。
    v_red=0・v_tau=0・全ブランクがΔの先頭（v_recの下限）を同時に達成した
    時点で，それ以上の解析はあり得ないので探索を打ち切る。

    戻り値：(v_red, v_tau, rec_positions) が辞書式最小の
    (atoms, tau, rec_positions, delta_after) のリスト（複数あれば同点で多義）。
    """
    templates = _atom_templates(p)
    seq = _align(p, tokens)
    n_atoms = len(templates)

    def resolve(pos, delta):
        """position pos の指示対象候補を，優先順位
        （Δ先頭優先）で (referent, 更新後delta, rec位置orNone) として返す。"""
        kind, j = seq[pos]
        if kind == "token":
            name, _ = _split_suffix(tokens[j])
            return [(name, _touch(delta, name), None)]
        return [(cand, _touch(delta, cand), i) for i, cand in enumerate(delta)]

    best = {"v": None, "items": [], "stop": False}
    first_pos = templates[0][1][0]

    def recurse(k, first_ref, delta, atoms, taus, rec, v_red, v_tau):
        if best["stop"]:
            return
        if best["v"] is not None and (v_red, v_tau) > best["v"][:2]:
            return  # v_red・v_tauの単調性による枝刈り
        if k == n_atoms:
            v = (v_red, v_tau, tuple(rec))
            if best["v"] is None or v < best["v"]:
                best["v"] = v
                best["items"] = [(list(atoms), tuple(taus), tuple(rec), delta)]
            elif v == best["v"]:
                best["items"].append((list(atoms), tuple(taus), tuple(rec), delta))
            if v_red == 0 and v_tau == 0 and all(x == 0 for x in rec):
                best["stop"] = True
            return

        r_pos, (i_pos, j_pos) = templates[k]
        rel_name, _ = _split_suffix(tokens[seq[r_pos][1]])
        for arg2, new_delta, rec_pos in resolve(j_pos, delta):
            is_blank = p[i_pos] == "_" or p[j_pos] == "_"
            if is_blank and arg2 == first_ref:
                continue  # H2: 共項排除
            args = (first_ref, arg2)
            for tau, free in _atom_tau_options(lex, rel_name, args):
                real = args if tau == 0 else tuple(reversed(args))
                key = (rel_name, real)
                blank_flags = (p[i_pos] == "_", p[j_pos] == "_")
                new_atom = (rel_name, args, bool(tau), blank_flags, key)
                new_v_red = _v_red(atoms + [new_atom], lex)
                new_v_tau = v_tau + (1 if (tau == 1 and free) else 0)
                if best["v"] is not None and (new_v_red, new_v_tau) > best["v"][:2]:
                    continue
                new_rec = rec + ([rec_pos] if rec_pos is not None else [])
                recurse(
                    k + 1,
                    arg2,
                    new_delta,
                    atoms + [new_atom],
                    taus + [tau],
                    new_rec,
                    new_v_red,
                    new_v_tau,
                )
                if best["stop"]:
                    return

    for first_ref, delta_after_first, rec_pos in resolve(first_pos, tuple(delta0)):
        rec0 = [rec_pos] if rec_pos is not None else []
        recurse(0, first_ref, delta_after_first, [], [], rec0, 0, 0)
        if best["stop"]:
            break

    if best["v"] is None:
        return []
    return [
        (
            [(rel, args, tr, bf) for rel, args, tr, bf, _ in atoms],
            taus,
            rec,
            delta_after,
        )
        for atoms, taus, rec, delta_after in best["items"]
    ]


def _candidates_for_pattern(lex: Lexicon, p: str, tokens, delta0: tuple):
    templates = _atom_templates(p)
    seq = _align(p, tokens)
    tau_choices = list(product(*_tau_options(templates))) if templates else [()]
    for referents, rec_positions, delta_after in _enumerate_resolutions(p, tokens, delta0):
        for tau in tau_choices:
            atoms = []
            for k, (r_pos, arg_positions) in enumerate(templates):
                rel_name, _ = _split_suffix(tokens[seq[r_pos][1]])
                args = tuple(referents[i] for i in arg_positions)
                blank_flags = tuple(p[i] == "_" for i in arg_positions)
                transposed = bool(tau[k]) if len(args) == 2 else False
                atoms.append((rel_name, args, transposed, blank_flags))
            yield atoms, tau, rec_positions, delta_after


def charitable_interpretation(lex: Lexicon, delta, tokens):
    """善意的解釈：線形文 tokens を先行詞リスト delta のもとで解析する。

    戻り値: (v が辞書式最小の解析のリスト, 探索で保持した候補)。
    枝刈りされた候補は第2成分に含まれない。
    最善解析が空なら非文（候補なし），複数あれば多義。

    違反ベクトル v = ⟨v_red, v_tau, v_rec, v_idx, v_pos⟩ の最後の成分
    v_pos は τ そのものの辞書式順序（転置の配置優先度）：p は v_idx で，
    g は (p, v_rec) で決定論的に一意になるので，最後まで残りうる自由度は
    τ の"個数が同じで配置が違う"ケースだけであり，v_pos を加えることで
    v の最小元は常にちょうど1つになる（強さのタイブレークは不要）。

    原子数2以上（交互型）のパターンは _search_chain の枝刈り探索を使う。
    多引数型・単独tは，そもそも読みが1原子しかなくv_redが常に0であり
    （比較対象がないので冗長になりようがない），アリティで自由度も
    抑えられているので，全列挙のままで十分速い。
    v_red=0・v_tau=0・全ブランクがΔ先頭という下限に達した時点で，
    それ以降の（優先度の低い）パターンはもう良い解析を出せないので
    探索を打ち切る。
    """
    delta0 = tuple(delta)
    candidates = []
    floor_hit = False
    for p, idx in sorted(_candidate_patterns(lex, tokens), key=lambda x: x[1]):
        if floor_hit:
            break
        if p.count("R") >= 2:
            local = _search_chain(lex, p, tokens, delta0)
        else:
            local = [
                (atoms, tau, rec_positions, delta_after)
                for atoms, tau, rec_positions, delta_after in _candidates_for_pattern(
                    lex, p, tokens, delta0
                )
                if _h1_sort_ok(lex, atoms) and _h2_coargument_ok(atoms)
            ]
        for atoms, tau, rec_positions, delta_after in local:
            v = (_v_red(atoms, lex), _v_tau(lex, atoms), rec_positions, idx, tau)
            candidates.append(
                Analysis(p, idx, tau, atoms, rec_positions, delta_after, v)
            )
            if v[0] == 0 and v[1] == 0 and all(x == 0 for x in rec_positions):
                floor_hit = True

    if not candidates:
        return [], []
    best_v = min(c.v for c in candidates)
    best = [c for c in candidates if c.v == best_v]
    return best, candidates


if __name__ == "__main__":
    patterns, unique_patterns = appline_list(max_length=5)
    for i, pats in enumerate(patterns):
        if pats:
            print(f"非ブランク長 {i}: {pats}")
    print("\n一意な語形:")
    for i, pats in enumerate(unique_patterns):
        if pats:
            print(f"非ブランク長 {i}: {pats}")

    # ---------- 体系Sの例 ----------
    print("\n--- 体系Sの例 ---")
    lex = Lexicon()
    lex.add_concept("person")
    for name in "abcd":
        lex.add_individual(name, "person")
    lex.add_relation("R", dom=("person", "person"))

    def show(tokens, delta):
        best, all_c = charitable_interpretation(lex, delta, tokens)
        print(f"文={' '.join(tokens)}  Δ={list(delta)}")
        if not best:
            print("  非文（候補なし）")
        else:
            for a in best:
                print(f"  読み: {a.reading_str()}  v={a.v}")

    show(["a", "R", "b", "R", "a"], [])  # aRbRa: 相互的な読みが選ばれる
    show(["a", "R", "R"], ["b"])  # aRR, Δ=[b]: 共項排除で一意に確定
    show(["a", "R"], ["b"])  # aR_: 共項排除でaRaが除外されaRbのみ残る
    show(["R"] * 12, ["a", "b", "c", "d"])  # R^12: 12本の異なる有向辺を使う

    show(["a", "R"], []) # 共項排除でaRaが除外されるため非文．
    show(["a", "R", "a"], [])

    repeated = [("R", ("a", "b"), False, (False, False))] * 2
    print(f"R(a,b) ∧ R(a,b): v_red={_v_red(repeated, lex)}")
    lex.add_relation("S", dom=("person", "person"))
    lex.add_implication("S", "R")
    stronger = repeated + [("S", ("a", "b"), False, (False, False))]
    print(f"R(a,b) ∧ R(a,b) ∧ S(a,b), S⇒R: v_red={_v_red(stronger, lex)}")


