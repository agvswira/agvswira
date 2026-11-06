"""Render the README's ./stats.sh card as terminal-style SVGs.

Writes stats/terminal-stats-dark.svg and stats/terminal-stats-light.svg.
Data comes from the GitHub GraphQL API and covers the last 12 months.
Rows whose value is zero are left out.

Usage:
  GITHUB_TOKEN=... python scripts/stats_card.py agvswira
  python scripts/stats_card.py --sample      # offline preview with fixed numbers
"""

import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

THEMES = {
    "dark": {"head": "#219ebc", "text": "#8b949e", "value": "#bde0fe"},
    "light": {"head": "#126782", "text": "#57606a", "value": "#24292f"},
}

FONT = "ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace"
SIZE = 14
CW = 8.4   # width of one monospace character at SIZE, forced with textLength
COLS = 48  # characters per line
PAD = 20
LINE = 24
TITLE = "last 12 months"


def streaks(counts: list[int]) -> tuple[int, int]:
    """Current and longest run of days with contributions, oldest day first.

    Today does not break the current streak until it is over, so a day
    with no contributions yet is skipped when it is the last one.
    """
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    days = counts[:-1] if counts and counts[-1] == 0 else counts
    current = 0
    for c in reversed(days):
        if not c:
            break
        current += 1
    return current, longest


def days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def fetch(login: str, token: str) -> list[tuple[str, int | str]]:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        sys.exit(f"GitHub API error: {data['errors']}")
    user = data["data"]["user"]
    cc = user["contributionsCollection"]
    calendar = cc["contributionCalendar"]
    counts = [d["contributionCount"] for w in calendar["weeks"] for d in w["contributionDays"]]
    current, longest = streaks(counts)
    return [
        ("contributions", calendar["totalContributions"]),
        ("commits", cc["totalCommitContributions"]),
        ("pull requests", cc["totalPullRequestContributions"]),
        ("public repos", user["repositories"]["totalCount"]),
        ("current streak", days(current) if current else 0),
        ("longest streak", days(longest) if longest else 0),
    ]


def sample() -> list[tuple[str, int | str]]:
    return [
        ("contributions", 274), ("commits", 170), ("pull requests", 1), ("public repos", 9),
        ("current streak", days(4)), ("longest streak", days(5)),
    ]


def text(y: float, cols: int, inner: str, color: str, bold: bool = False) -> str:
    weight = ' font-weight="700"' if bold else ""
    return (
        f'<text x="{PAD}" y="{y}" fill="{color}"{weight} textLength="{cols * CW:.1f}" '
        f'lengthAdjust="spacingAndGlyphs" xml:space="preserve">{inner}</text>'
    )


def render(rows: list[tuple[str, int | str]], theme: dict) -> str:
    rows = [(label, value) for label, value in rows if value]
    y = PAD + SIZE
    out = [text(y, len(TITLE), TITLE, theme["head"], bold=True)]
    summary = []
    for label, value in rows:
        y += LINE
        val = f"{value:,}" if isinstance(value, int) else value
        dots = "." * (COLS - len(label) - len(val) - 2)
        inner = f'{escape(label)} {dots} <tspan fill="{theme["value"]}" font-weight="700">{val}</tspan>'
        out.append(text(y, COLS, inner, theme["text"]))
        summary.append(f"{label}: {val}")

    width = round(PAD * 2 + COLS * CW)
    height = round(y + PAD - 4)
    desc = escape(f"GitHub stats, {TITLE}. " + ", ".join(summary))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{desc}">\n'
        f"<title>{desc}</title>\n"
        f'<g font-family="{FONT}" font-size="{SIZE}">\n' + "\n".join(out) + "\n</g>\n</svg>\n"
    )


def main() -> None:
    args = sys.argv[1:]
    if args == ["--sample"]:
        rows = sample()
    elif len(args) == 1:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("GITHUB_TOKEN is not set")
        rows = fetch(args[0], token)
    else:
        sys.exit(__doc__)

    out_dir = Path("stats")
    out_dir.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = out_dir / f"terminal-stats-{name}.svg"
        path.write_text(render(rows, theme), encoding="utf-8", newline="\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
