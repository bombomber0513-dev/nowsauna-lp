"""教訓帳（.claude/rules/lessons.md）の点検・受信箱の集計・回数の反映。

使い方:
  python lessons/tools/lessons.py check
  python lessons/tools/lessons.py inbox
  python lessons/tools/lessons.py tally [--apply]
  python lessons/tools/lessons.py archive [--apply]
  python lessons/tools/lessons.py skills
  python lessons/tools/lessons.py pending

ID は先頭1文字＋3桁（sns は L、realestate は R、nowsauna-lp は N で新規を振る。他リポから持ち込んだ項目は元の番号のまま）。

教訓の文面を足す・まとめる・消すのは /lessons（Claude）が Edit で行う。
このスクリプトは書式の点検と、✔/✖ の回数・ファイル移動のような機械的な処理だけを受け持つ。
"""
import csv
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / ".claude" / "rules" / "lessons.md"
INBOX = ROOT / "lessons" / "inbox"
ARCHIVE = ROOT / "lessons" / "archive"
STATS = ROOT / "lessons" / "stats.csv"
LIMIT = 30

ITEM_RE = re.compile(r"^- \[([A-Z]\d{3,})\] ✔(\d+) ✖(\d+) \| (.+)$")
EVAL_RE = re.compile(r"^- ([A-Z]\d{3,}):\s*([✔✖])")
KIND_RE = re.compile(r"^- 種類:\s*(\S+)")
TRIGGER_RE = re.compile(r"^- きっかけ:\s*(.+)$")
PROC_RE = re.compile(r"^- 手順:\s*([^／/（(]+)")
SKILL_THRESHOLD = 3
# 週1整理でまとめて扱うリポ（このリポと同じ親フォルダに clone されている前提）
REPOS = ["sns", "realestate", "nowsauna-lp"]


def read_book():
    text = BOOK.read_text(encoding="utf-8")
    start = text.index("<!-- lessons:start -->")
    end = text.index("<!-- lessons:end -->")
    return text, start, end


def items(text, start, end):
    out = []
    for line in text[start:end].splitlines()[1:]:
        if not line.strip():
            continue
        m = ITEM_RE.match(line)
        out.append((line, m))
    return out


def inbox_files():
    return sorted(p for p in INBOX.glob("*.md") if not p.name.startswith("_"))


def parse_inbox(path):
    kinds, triggers, evals = [], [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if m := KIND_RE.match(line):
            kinds.append(m.group(1))
        elif m := TRIGGER_RE.match(line):
            triggers.append(m.group(1).strip())
        elif m := EVAL_RE.match(line):
            evals.append((m.group(1), m.group(2)))
    return kinds, triggers, evals


def cmd_check():
    text, start, end = read_book()
    problems, seen = [], set()
    rows = items(text, start, end)
    for line, m in rows:
        if not m:
            problems.append(f"書式違い: {line}")
            continue
        lid, ok, ng = m.group(1), int(m.group(2)), int(m.group(3))
        if lid in seen:
            problems.append(f"ID重複: {lid}")
        seen.add(lid)
        if ng - ok >= 2:
            problems.append(f"削除候補（✖が✔を2以上上回る）: {lid}")
    if len(rows) > LIMIT:
        problems.append(f"上限超え: {len(rows)}項目（上限{LIMIT}）")
    print(f"教訓 {len(rows)}項目 / 受信箱 {len(inbox_files())}件")
    for p in problems:
        print("⚠", p)
    return 1 if any(p.startswith(("書式違い", "ID重複")) for p in problems) else 0


def cmd_inbox():
    files = inbox_files()
    if not files:
        print("受信箱は空です")
        return 0
    for path in files:
        kinds, triggers, evals = parse_inbox(path)
        print(f"■ {path.name}  教訓{len(kinds)}件 {' '.join(kinds)}  評価: "
              + (", ".join(f"{i}{s}" for i, s in evals) or "なし"))
    return 0


def cmd_skills():
    """受信箱と保管庫の「繰り返した手順」を数え、3回以上のものをスキル化候補として出す。"""
    files = inbox_files() + sorted(ARCHIVE.glob("*/*.md"))
    counts = {}
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = PROC_RE.match(line)
            if not m:
                continue
            name = m.group(1).strip()
            if not name or name.startswith("短い名前"):
                continue
            counts.setdefault(name, []).append(path.name)
    skills_dir = ROOT / ".claude" / "skills"
    existing = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    found = False
    for name, srcs in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        mark = "★候補" if len(srcs) >= SKILL_THRESHOLD else "  "
        found = found or len(srcs) >= SKILL_THRESHOLD
        print(f"{mark} {name}: {len(srcs)}回（{', '.join(srcs)}）")
    if not counts:
        print("繰り返した手順の記録はまだありません")
    elif not found:
        print(f"スキル化候補（{SKILL_THRESHOLD}回以上）はまだありません")
    print(f"既存スキル: {', '.join(sorted(existing))}")
    return 0


def cmd_tally(apply):
    text, start, end = read_book()
    delta = {}
    for path in inbox_files():
        for lid, sign in parse_inbox(path)[2]:
            d = delta.setdefault(lid, [0, 0])
            d[0 if sign == "✔" else 1] += 1
    if not delta:
        print("反映する評価はありません")
        return 0
    body = text[start:end]
    for lid, (ok, ng) in sorted(delta.items()):
        pat = re.compile(rf"^- \[{lid}\] ✔(\d+) ✖(\d+) \|", re.M)
        m = pat.search(body)
        if not m:
            print(f"⚠ {lid} は教訓帳に無いので飛ばします")
            continue
        new = f"- [{lid}] ✔{int(m.group(1)) + ok} ✖{int(m.group(2)) + ng} |"
        print(f"{lid}: ✔+{ok} ✖+{ng} → {new}")
        body = body[:m.start()] + new + body[m.end():]
    if apply:
        BOOK.write_text(text[:start] + body + text[end:], encoding="utf-8")
        print("教訓帳に書き込みました")
    else:
        print("（確認のみ。書き込むには --apply）")
    return 0


def cmd_archive(apply):
    files = inbox_files()
    if not files:
        print("移すものはありません")
        return 0
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()  # JST（定時実行はUTCの日曜に動くため）
    year, week, _ = today.isocalendar()
    counts = {"訂正": 0, "手戻り": 0, "CI失敗": 0, "失敗": 0, "成功": 0}
    for path in files:
        kinds, triggers, _ = parse_inbox(path)
        for k in kinds:
            if k in counts:
                counts[k] += 1
        for t in triggers:
            for key, word in (("訂正", "訂正"), ("手戻り", "手戻り"), ("CI失敗", "CI失敗")):
                if word in t:
                    counts[key] += 1
    row = [today.isoformat(), f"{year}-W{week:02d}", len(files)] + list(counts.values())
    print("stats.csv に足す行:", row)
    dest = ARCHIVE / today.strftime("%Y-%m")
    for path in files:
        print(f"{path.name} → {dest.relative_to(ROOT)}/")
    if not apply:
        print("（確認のみ。実行するには --apply）")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.move(str(path), dest / path.name)
    new = not STATS.exists()
    with STATS.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "week", "files", "corrections", "rework", "ci_fail", "failures", "successes"])
        w.writerow(row)
    print("移動と集計を書き込みました")
    return 0


def cmd_pending():
    """各リポの受信箱の件数だけを数える（中身は読まない）。0件のリポは週1整理で開かずに飛ばす。"""
    total = 0
    for name in REPOS:
        inbox = ROOT.parent / name / "lessons" / "inbox"
        if not inbox.is_dir():
            print(f"{name}: 教訓帳なし（clone されていないか未導入）")
            continue
        n = sum(1 for p in inbox.glob("*.md") if not p.name.startswith("_"))
        total += n
        print(f"{name}: {n}件")
    print(f"合計 {total}件" + ("（全リポ空なので今週の整理は無し）" if total == 0 else ""))
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, apply = argv[0], "--apply" in argv
    if cmd == "check":
        return cmd_check()
    if cmd == "inbox":
        return cmd_inbox()
    if cmd == "tally":
        return cmd_tally(apply)
    if cmd == "archive":
        return cmd_archive(apply)
    if cmd == "skills":
        return cmd_skills()
    if cmd == "pending":
        return cmd_pending()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
