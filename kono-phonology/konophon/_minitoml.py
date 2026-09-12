"""TOML の最小読み取り（``tomllib`` / ``tomli`` が無い環境のための予備）.

**汎用の TOML パーサではない．** ``data/phonology.toml`` が使っている部分集合
だけを扱う:

- ``[table]`` / ``[[array_of_tables]]``（ドット区切りのキーを含む）
- ``key = value``（基本文字列・整数・浮動小数・真偽値）
- 配列 ``[a, b, c]``（複数行可）
- インラインテーブル ``{ a = 1, b = "x" }``
- ``#`` 以降のコメント（文字列の中は除く）

対応しないもの: 複数行文字列、リテラル文字列 ``'...'`` の一部エスケープ、
日付時刻、指数表記以外の特殊数値、ドット区切りの代入 ``a.b = 1``．

正しさは ``tests/test_minitoml.py`` で ``tomllib`` の出力と完全一致することを
検証している（Python 3.11 以上のときのみ実行される）．
"""

from __future__ import annotations

from typing import Any

__all__ = ["loads"]


class TomlError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    out = []
    in_str = False
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\" and quote == '"':
                out.append(ch)
                i += 1
                if i < len(line):
                    out.append(line[i])
                    i += 1
                continue
            if ch == quote:
                in_str = False
            out.append(ch)
        else:
            if ch == "#":
                break
            if ch in "\"'":
                in_str = True
                quote = ch
            out.append(ch)
        i += 1
    return "".join(out)


def _unescape(s: str) -> str:
    out = []
    i = 0
    table = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "b": "\b", "f": "\f"}
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            c = s[i + 1]
            if c in table:
                out.append(table[c])
                i += 2
                continue
            if c == "u" and i + 5 < len(s) + 1:
                out.append(chr(int(s[i + 2 : i + 6], 16)))
                i += 6
                continue
            if c == "U":
                out.append(chr(int(s[i + 2 : i + 10], 16)))
                i += 10
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _split_top(text: str, sep: str) -> list[str]:
    """括弧・引用符の外側の ``sep`` で分割する."""
    parts, buf = [], []
    depth = 0
    in_str = False
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\" and quote == '"':
                buf.append(ch)
                i += 1
                if i < len(text):
                    buf.append(text[i])
                    i += 1
                continue
            if ch == quote:
                in_str = False
            buf.append(ch)
        elif ch in "\"'":
            in_str = True
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _parse_value(raw: str) -> Any:
    v = raw.strip()
    if not v:
        raise TomlError("空の値")
    if v[0] == '"' and v[-1] == '"' and len(v) >= 2:
        return _unescape(v[1:-1])
    if v[0] == "'" and v[-1] == "'" and len(v) >= 2:
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    if v[0] == "[":
        if v[-1] != "]":
            raise TomlError(f"配列が閉じていない: {v!r}")
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(x) for x in _split_top(inner, ",") if x.strip()]
    if v[0] == "{":
        if v[-1] != "}":
            raise TomlError(f"インラインテーブルが閉じていない: {v!r}")
        d: dict[str, Any] = {}
        for item in _split_top(v[1:-1], ","):
            if not item.strip():
                continue
            k, _, val = item.partition("=")
            d[_parse_key(k.strip())[-1]] = _parse_value(val)
        return d
    cleaned = v.replace("_", "")
    try:
        return int(cleaned)
    except ValueError:
        pass
    try:
        return float(cleaned)
    except ValueError:
        pass
    raise TomlError(f"値を解釈できない: {v!r}")


def _parse_key(raw: str) -> list[str]:
    out = []
    for part in _split_top(raw.strip(), "."):
        p = part.strip()
        if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'":
            out.append(_unescape(p[1:-1]) if p[0] == '"' else p[1:-1])
        else:
            if not p:
                raise TomlError(f"空のキー: {raw!r}")
            out.append(p)
    return out


def _descend(root: dict, path: list[str]) -> dict:
    cur = root
    for k in path:
        nxt = cur.setdefault(k, {})
        if isinstance(nxt, list):
            nxt = nxt[-1]
        if not isinstance(nxt, dict):
            raise TomlError(f"キーの衝突: {'.'.join(path)}")
        cur = nxt
    return cur


def loads(text: str) -> dict:
    root: dict[str, Any] = {}
    cur = root
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i]).strip()
        i += 1
        if not line:
            continue
        if line.startswith("[["):
            if not line.endswith("]]"):
                raise TomlError(f"表ヘッダが閉じていない: {line!r}")
            path = _parse_key(line[2:-2])
            parent = _descend(root, path[:-1])
            arr = parent.setdefault(path[-1], [])
            if not isinstance(arr, list):
                raise TomlError(f"配列表と衝突: {line!r}")
            cur = {}
            arr.append(cur)
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise TomlError(f"表ヘッダが閉じていない: {line!r}")
            cur = _descend(root, _parse_key(line[1:-1]))
            continue
        if "=" not in line:
            raise TomlError(f"解釈できない行: {line!r}")
        key, _, val = line.partition("=")
        val = val.strip()
        # 配列・インラインテーブルが複数行にまたがる場合は連結する
        while val.count("[") > val.count("]") or val.count("{") > val.count("}"):
            if i >= len(lines):
                raise TomlError(f"括弧が閉じないまま終端: {line!r}")
            val += " " + _strip_comment(lines[i]).strip()
            i += 1
        path = _parse_key(key)
        target = _descend(cur, path[:-1]) if len(path) > 1 else cur
        target[path[-1]] = _parse_value(val)
    return root
