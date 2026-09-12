#!/usr/bin/env python3
"""Issue tracker for kono-main/detail.

Usage:
    python issues.py list              # 全issueの一覧
    python issues.py list --open       # openのみ
    python issues.py list --file X     # ファイル絞り込み
    python issues.py show KONO-0001    # 詳細表示
    python issues.py search <keyword>  # キーワード検索
    python issues.py assign            # 未採番マーカーにIDを自動付与 (dry-run)
    python issues.py assign --apply    # 実際に書き込む
    python issues.py sync              # .texのissueとJSONのmarkersを照合
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

DETAIL_DIR = Path(__file__).resolve().parent.parent  # detail/
CHAPTERS_DIR = DETAIL_DIR / "chapters"
TASKS_JSON = DETAIL_DIR.parent / "archive" / "archive001" / "IssueTracker" / "data" / "kono_tasks_rec.json"

ISSUE_RE = re.compile(r"%\s*@issue\s+(KONO-\d+)")
MARKER_RE = re.compile(r"^(.*)(\\(?:todo|memo|fixme))\{")
# \memo にはissue IDを付与しない（メモは追跡対象外）
ASSIGNABLE_MARKER_RE = re.compile(r"^(.*)(\\(?:todo|fixme))\{")
ID_PREFIX = "KONO-"


def find_tex_files():
    return sorted(CHAPTERS_DIR.rglob("*.tex"))


def scan_issues():
    """Scan all .tex files and return a list of issue dicts."""
    issues = []
    for path in find_tex_files():
        relpath = str(path.relative_to(DETAIL_DIR))
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            m = ISSUE_RE.search(line)
            if m:
                issue_id = m.group(1)
                marker_type = None
                marker_text = ""
                # look at the next non-blank line for the marker
                for j in range(i + 1, min(i + 3, len(lines))):
                    mm = MARKER_RE.match(lines[j])
                    if mm:
                        marker_type = mm.group(2).lstrip("\\")
                        # extract text until closing brace (may span lines)
                        rest = lines[j][mm.end():]
                        depth = 1
                        buf = []
                        for k in range(j, len(lines)):
                            segment = lines[k] if k > j else rest
                            for ch in segment:
                                if ch == "{":
                                    depth += 1
                                elif ch == "}":
                                    depth -= 1
                                    if depth == 0:
                                        break
                                buf.append(ch)
                            if depth == 0:
                                break
                            if k > j:
                                buf.append("\n")
                        marker_text = "".join(buf).strip()
                        break
                issues.append({
                    "id": issue_id,
                    "file": relpath,
                    "line": i + 1,
                    "type": marker_type or "?",
                    "text": marker_text[:200],
                })
    return issues


def scan_untagged():
    """Find \\todo/\\fixme lines without a preceding @issue tag (\\memo is excluded)."""
    untagged = []
    for path in find_tex_files():
        relpath = str(path.relative_to(DETAIL_DIR))
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines):
            if ASSIGNABLE_MARKER_RE.match(line):
                # check if preceding line has @issue
                has_tag = False
                if i > 0 and ISSUE_RE.search(lines[i - 1]):
                    has_tag = True
                # also check if the marker is inside a comment
                stripped = line.lstrip()
                if stripped.startswith("%"):
                    continue
                if not has_tag:
                    untagged.append({
                        "file": relpath,
                        "line": i + 1,
                        "content": line.strip()[:120],
                    })
    return untagged


def next_id(existing_issues):
    max_num = 0
    for iss in existing_issues:
        num = int(iss["id"].replace(ID_PREFIX, ""))
        max_num = max(max_num, num)
    return max_num + 1


def load_tasks_json():
    if TASKS_JSON.exists():
        return json.loads(TASKS_JSON.read_text())
    return {}


def collect_markers_from_json(node, path="", results=None):
    """Recursively collect all markers fields from the task tree."""
    if results is None:
        results = {}
    name = path
    if "markers" in node:
        results[name] = node["markers"]
    for key, child in node.get("children", {}).items():
        child_path = f"{path}/{key}" if path else key
        if isinstance(child, dict):
            collect_markers_from_json(child, child_path, results)
    return results


# ── Commands ──

def cmd_list(args):
    issues = scan_issues()
    if args.open:
        # filter by checking JSON status
        tasks = load_tasks_json()
        marker_to_task = {}
        def walk(node, name=""):
            if "markers" in node:
                for m in node["markers"]:
                    marker_to_task[m] = node.get("status", "open")
            for k, child in node.get("children", {}).items():
                if isinstance(child, dict):
                    walk(child, k)
        walk(tasks)
        issues = [i for i in issues if marker_to_task.get(i["id"], "open") == "open"]
    if args.file:
        issues = [i for i in issues if args.file in i["file"]]

    if not issues:
        print("No issues found.")
        return

    for iss in sorted(issues, key=lambda x: x["id"]):
        tag = iss["type"].upper()
        text_preview = iss["text"][:60].replace("\n", " ")
        print(f"  {iss['id']}  [{tag:5s}]  {iss['file']}:{iss['line']}  {text_preview}")
    print(f"\n  Total: {len(issues)}")


def cmd_show(args):
    issues = scan_issues()
    target = args.issue_id.upper()
    found = [i for i in issues if i["id"] == target]
    if not found:
        print(f"Issue {target} not found.")
        return
    iss = found[0]
    print(f"  ID:   {iss['id']}")
    print(f"  Type: {iss['type']}")
    print(f"  File: {iss['file']}:{iss['line']}")
    print(f"  Text:")
    for line in iss["text"].split("\n"):
        print(f"    {line}")

    # check JSON
    tasks = load_tasks_json()
    def find_in_tree(node, name=""):
        if not isinstance(node, dict):
            return None
        if "markers" in node and iss["id"] in node["markers"]:
            return name, node
        for key, val in node.items():
            if key == "children" and isinstance(val, dict):
                for k, child in val.items():
                    result = find_in_tree(child, k)
                    if result:
                        return result
            elif isinstance(val, dict) and key != "markers":
                result = find_in_tree(val, key)
                if result:
                    return result
        return None
    result = find_in_tree(tasks)
    if result:
        task_name, task_node = result
        print(f"  Task: {task_name}")
        if "status" in task_node:
            print(f"  Status: {task_node['status']}")
        if "note" in task_node:
            print(f"  Note: {task_node['note']}")
    else:
        print(f"  Task: (not linked in kono_tasks_rec.json)")


def cmd_search(args):
    issues = scan_issues()
    query = args.keyword.lower()
    matched = [i for i in issues if query in i["text"].lower() or query in i["file"].lower() or query in i["type"].lower()]
    if not matched:
        print(f"No issues matching '{args.keyword}'.")
        return
    for iss in matched:
        text_preview = iss["text"][:60].replace("\n", " ")
        print(f"  {iss['id']}  [{iss['type']:5s}]  {iss['file']}:{iss['line']}  {text_preview}")
    print(f"\n  {len(matched)} match(es)")


def cmd_assign(args):
    existing = scan_issues()
    untagged = scan_untagged()

    if not untagged:
        print("All markers already have issue IDs.")
        return

    nid = next_id(existing)

    assignments = []
    for item in untagged:
        issue_id = f"{ID_PREFIX}{nid:04d}"
        assignments.append({**item, "id": issue_id})
        nid += 1

    print(f"Found {len(untagged)} untagged marker(s):\n")
    for a in assignments:
        print(f"  {a['id']}  {a['file']}:{a['line']}  {a['content'][:80]}")

    if not args.apply:
        print(f"\nDry run. Use --apply to write.")
        return

    # group by file and apply (insert from bottom to top to preserve line numbers)
    by_file = {}
    for a in assignments:
        by_file.setdefault(a["file"], []).append(a)

    for relpath, items in by_file.items():
        path = DETAIL_DIR / relpath
        lines = path.read_text().splitlines(keepends=True)
        # sort by line desc so insertions don't shift later indices
        for item in sorted(items, key=lambda x: -x["line"]):
            idx = item["line"] - 1  # 0-indexed
            indent = re.match(r"^(\s*)", lines[idx]).group(1)
            tag_line = f"{indent}% @issue {item['id']}\n"
            lines.insert(idx, tag_line)
        path.write_text("".join(lines))

    print(f"\nAssigned {len(assignments)} issue ID(s).")


def cmd_sync(args):
    """Check consistency between .tex @issue tags and JSON markers."""
    tex_issues = {i["id"] for i in scan_issues()}
    tasks = load_tasks_json()
    json_markers = set()

    def walk(node):
        if not isinstance(node, dict):
            return
        for m in node.get("markers", []):
            if m.startswith(ID_PREFIX):
                json_markers.add(m)
        for key, val in node.items():
            if key == "children" and isinstance(val, dict):
                for child in val.values():
                    walk(child)
            elif isinstance(val, dict) and key != "markers":
                walk(val)
    walk(tasks)

    in_tex_not_json = tex_issues - json_markers
    in_json_not_tex = json_markers - tex_issues

    if in_tex_not_json:
        print("In .tex but not in JSON (unlinked):")
        for i in sorted(in_tex_not_json):
            print(f"  {i}")
    if in_json_not_tex:
        print("In JSON but not in .tex (stale reference):")
        for i in sorted(in_json_not_tex):
            print(f"  {i}")
    if not in_tex_not_json and not in_json_not_tex:
        print("All synced.")
    print(f"\n  .tex: {len(tex_issues)} issue(s), JSON: {len(json_markers)} reference(s)")


def main():
    parser = argparse.ArgumentParser(description="Issue tracker for kono-main/detail")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", aliases=["ls"], help="List all issues")
    p_list.add_argument("--open", action="store_true", help="Show only open issues")
    p_list.add_argument("--file", type=str, help="Filter by file path substring")

    p_show = sub.add_parser("show", help="Show issue details")
    p_show.add_argument("issue_id", type=str)

    p_search = sub.add_parser("search", aliases=["grep"], help="Search by keyword")
    p_search.add_argument("keyword", type=str)

    p_assign = sub.add_parser("assign", help="Auto-assign IDs to untagged markers")
    p_assign.add_argument("--apply", action="store_true", help="Actually write (default is dry-run)")

    p_sync = sub.add_parser("sync", help="Check .tex ↔ JSON consistency")

    args = parser.parse_args()
    if args.command in ("list", "ls"):
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command in ("search", "grep"):
        cmd_search(args)
    elif args.command == "assign":
        cmd_assign(args)
    elif args.command == "sync":
        cmd_sync(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
