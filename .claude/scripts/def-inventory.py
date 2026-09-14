#!/usr/bin/env python3
"""章の定義単位を列挙し，定義票の雛形を出す（規範照合の材料）．
使い方: python3 .claude/scripts/def-inventory.py <chapter.tex>
拾うもの（有効本文のみ）: \\rele{X}{A}{B}{訳}，forest の \\tn{X}{訳}，definition 環境，whynot／memo／todo の数．
各語について「属＋種差／署名／存在条件と同一性の様式／開閉ハブと射影／判定テスト／境界例／動機の実例／出典」の欄を空で出す．
"""
import re, sys, os, importlib.util
_spec = importlib.util.spec_from_file_location("active_lines", os.path.join(os.path.dirname(os.path.abspath(__file__)), "active-lines.py"))
_al = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_al); ranges = _al.ranges

def main(path):
    act, _, _ = ranges(path)
    lines = open(path, encoding="utf-8").read().split("\n")
    active = set()
    for a, b in act: active.update(range(a, b + 1))
    body = "\n".join(l for i, l in enumerate(lines, 1) if i in active and not l.lstrip().startswith("%"))
    rele = re.findall(r"\\rele\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}", body)
    nodes = re.findall(r"\\tn\{([^}]*)\}\{([^}]*)\}", body)
    defs = len(re.findall(r"\\begin\{definition\}", body))
    counts = {k: len(re.findall(r"\\begin\{%s\}" % k if k == "whynot" else r"\\%s\{" % k, body)) for k in ("whynot", "memo", "todo", "ques")}
    print(f"# 定義票の雛形: {path}")
    print(f"definition 環境 {defs}，whynot {counts['whynot']}，memo {counts['memo']}，todo {counts['todo']}，ques {counts['ques']}\n")
    print("## 節点（木）")
    for x, tr in nodes:
        print(f"- **{x}**（{tr}）：属＋種差＝ ／ 存在条件・同一性の様式＝ ／ 統一関係＝ ／ 開閉ハブと射影＝ ／ 判定テスト＝ ／ 境界例＝ ／ 動機の実例＝ ／ 出典＝")
    print("\n## 関係（\\rele）")
    for x, a, b, tr in rele:
        print(f"- **{x}**：{a}×{b}「{tr}」：公理（推移・反対称・補充）＝ ／ 三項由来か＝ ／ 辞書 arguments 照合＝ ／ 判定テスト＝ ／ 境界例＝")
    print("\n## 攻撃工程の 5 検査（各候補に）: 設計規範への適合／剛性タグ／同一性の様式の宣言／新装置の立証責任／見做しの規則性")

if __name__ == "__main__":
    main(sys.argv[1])
