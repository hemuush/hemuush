"""Generate self-hosted GitHub stats SVG cards (no third-party services).

Usage: GITHUB_TOKEN=... python scripts/generate_stats.py <username> <out_dir>
Writes stats-{dark,light}.svg and langs-{dark,light}.svg
"""
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

THEMES = {
    "dark": dict(bg="#0D1424", bd="#1E293B", title="#38BDF8", text="#E2E8F0", mut="#94A3B8", track="#1E293B"),
    "light": dict(bg="#FFFFFF", bd="#D0D7DE", title="#0284C7", text="#0F172A", mut="#57606A", track="#E5E7EB"),
}
FONT = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


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


def card(w, h, t, inner, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">'
        f'<style>.f{{font-family:{FONT}}}@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}'
        f'.r{{animation:in .6s ease both}}@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}'
        f'.bar{{transform-origin:left;transform-box:fill-box;animation:grow 1s ease both}}</style>'
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="{t["bg"]}" stroke="{t["bd"]}"/>'
        f'<text class="f" x="24" y="38" font-size="17" font-weight="700" fill="{t["title"]}">{escape(title)}</text>'
        f"{inner}</svg>"
    )


def stats_svg(d, t, login):
    rows = [("Total commits (last year)", d["commits"]), ("Pull requests", d["prs"]), ("Issues", d["issues"]),
            ("Stars earned", d["stars"]), ("Public repositories", d["repos"]), ("Followers", d["followers"])]
    out = []
    for i, (k, v) in enumerate(rows):
        y = 74 + i * 28
        out.append(
            f'<g class="r" style="animation-delay:{i*.08:.2f}s"><text class="f" x="24" y="{y}" font-size="14" fill="{t["mut"]}">{k}</text>'
            f'<text class="f" x="371" y="{y}" font-size="14" font-weight="700" text-anchor="end" fill="{t["text"]}">{v:,}</text></g>'
        )
    return card(395, 250, t, "".join(out), f"{login}'s GitHub stats")


def langs_svg(d, t):
    items = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[0] for _, v in items) or 1
    out = []
    for i, (name, (size, color)) in enumerate(items):
        y = 72 + i * 28
        pct = size / total * 100
        out.append(
            f'<g class="r" style="animation-delay:{i*.08:.2f}s"><text class="f" x="24" y="{y}" font-size="13" fill="{t["text"]}">{escape(name)}</text>'
            f'<text class="f" x="371" y="{y}" font-size="13" text-anchor="end" fill="{t["mut"]}">{pct:.1f}%</text>'
            f'<rect x="24" y="{y+7}" width="347" height="7" rx="3.5" fill="{t["track"]}"/>'
            f'<rect class="bar" style="animation-delay:{i*.08:.2f}s" x="24" y="{y+7}" width="{max(347*pct/100,4):.1f}" height="7" rx="3.5" fill="{color}"/></g>'
        )
    return card(395, 250, t, "".join(out), "Top languages")


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    d = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else fetch(login, os.environ["GITHUB_TOKEN"])
    for name, t in THEMES.items():
        open(os.path.join(out_dir, f"stats-{name}.svg"), "w").write(stats_svg(d, t, login))
        open(os.path.join(out_dir, f"langs-{name}.svg"), "w").write(langs_svg(d, t))


if __name__ == "__main__":
    main()
