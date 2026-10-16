"""Generate self-hosted GitHub stats SVG cards (no third-party services).

Usage: GITHUB_TOKEN=... python scripts/generate_stats.py <username> <out_dir>
Writes stats-{dark,light}.svg and langs-{dark,light}.svg
"""
import base64
import json
import os
import sys
import urllib.request
from html import escape

QUERY = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    pullRequests{totalCount}
    issues{totalCount}
    contributionsCollection{totalCommitContributions restrictedContributionsCount}
    repositories(ownerAffiliations:OWNER,isFork:false,first:100,orderBy:{field:PUSHED_AT,direction:DESC}){
      totalCount
      nodes{stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}
    }
  }
}"""

# Matches the portfolio site: black card, crimson accent, Anton display type
THEME = dict(bg="#070707", bd="#222224", ac="#E0262F", text="#F1EFEA", mut="#8E8B86", line="#222224")
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
ANTON = base64.b64encode(
    open(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "anton-sub.woff2"), "rb").read()
).decode()


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    u = body["data"]["user"]
    repos = u["repositories"]["nodes"]
    cc = u["contributionsCollection"]
    langs = {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            n = e["node"]
            cur = langs.setdefault(n["name"], [0, n["color"] or "#8B949E"])
            cur[0] += e["size"]
    return dict(
        commits=cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        prs=u["pullRequests"]["totalCount"],
        issues=u["issues"]["totalCount"],
        stars=sum(r["stargazerCount"] for r in repos),
        repos=u["repositories"]["totalCount"],
        followers=u["followers"]["totalCount"],
        langs=langs,
    )


def card(w, h, inner, title):
    t = THEME
    star = "M0 -6L1.6 -1.6L6 0L1.6 1.6L0 6L-1.6 1.6L-6 0L-1.6 -1.6Z"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f"<style>@font-face{{font-family:AntonE;src:url(data:font/woff2;base64,{ANTON}) format('woff2')}}"
        f".f{{font-family:{FONT}}}.d{{font-family:AntonE,Impact,'Arial Narrow',sans-serif}}"
        f"@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}"
        f".r{{animation:in .6s cubic-bezier(.22,.8,.2,1) both}}@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
        f".bar{{transform-origin:left;transform-box:fill-box;animation:grow 1s cubic-bezier(.22,.8,.2,1) both}}</style>"
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" fill="{t["bg"]}" stroke="{t["bd"]}"/>'
        f'<text class="f" x="24" y="30" font-size="10" font-weight="500" letter-spacing="1.6" fill="{t["ac"]}">GITHUB · LIVE</text>'
        f'<text class="d" x="24" y="60" font-size="26" letter-spacing=".5" fill="{t["text"]}">{escape(title.upper())}</text>'
        f'<path d="{star}" transform="translate({w-30},26)" fill="{t["ac"]}"/>'
        f"{inner}</svg>"
    )


def stats_svg(d, login):
    t = THEME
    rows = [("Commits · last year", d["commits"]), ("Pull requests", d["prs"]), ("Public repos", d["repos"]),
            ("Stars earned", d["stars"]), ("Issues", d["issues"]), ("Followers", d["followers"])]
    out = []
    for i, (k, v) in enumerate(rows):
        col, row = i % 2, i // 2
        x, y = 24 + col * 178, 76 + row * 58
        out.append(
            f'<g class="r" style="animation-delay:{i*.07:.2f}s">'
            f'<line x1="{x}" y1="{y}" x2="{x+164}" y2="{y}" stroke="{t["line"]}"/>'
            f'<text class="f" x="{x}" y="{y+17}" font-size="9.5" font-weight="500" letter-spacing="1.3" fill="{t["mut"]}">{escape(k.upper())}</text>'
            f'<text class="d" x="{x}" y="{y+49}" font-size="30" fill="{t["ac"]}">{v:,}</text></g>'
        )
    return card(395, 260, "".join(out), "GitHub stats")


def langs_svg(d):
    t = THEME
    items = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[0] for _, v in items) or 1
    out = []
    for i, (name, (size, _color)) in enumerate(items):
        y = 92 + i * 27
        pct = size / total * 100
        op = max(1 - i * 0.15, 0.3)
        out.append(
            f'<g class="r" style="animation-delay:{i*.07:.2f}s"><text class="f" x="24" y="{y}" font-size="10.5" font-weight="500" letter-spacing="1.2" fill="{t["text"]}">{escape(name.upper())}</text>'
            f'<text class="d" x="371" y="{y+1}" font-size="15" text-anchor="end" fill="{t["ac"]}">{pct:.1f}%</text>'
            f'<rect x="24" y="{y+7}" width="347" height="3" fill="{t["line"]}"/>'
            f'<rect class="bar" style="animation-delay:{i*.07:.2f}s" x="24" y="{y+7}" width="{max(347*pct/100,3):.1f}" height="3" fill="{t["ac"]}" fill-opacity="{op:.2f}"/></g>'
        )
    return card(395, 260, "".join(out), "Top languages")


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    d = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else fetch(login, os.environ["GITHUB_TOKEN"])
    stats, langs = stats_svg(d, login), langs_svg(d)
    for name in ("dark", "light"):  # same design for both; README picks by colour scheme
        open(os.path.join(out_dir, f"stats-{name}.svg"), "w").write(stats)
        open(os.path.join(out_dir, f"langs-{name}.svg"), "w").write(langs)


if __name__ == "__main__":
    main()
