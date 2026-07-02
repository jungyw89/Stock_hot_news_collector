#!/usr/bin/env python3
"""
Unified social report for a stock ticker across X (Twitter), Reddit, and StockTwits.

Usage:
    python scripts/social_report.py O "Realty Income" --days 2 --limit 12
    python scripts/social_report.py NVDA "NVIDIA" --days 1

Sources:
  - StockTwits : public JSON API (no auth) — includes native Bullish/Bearish tags
  - X/Twitter  : twitter-cli (reads cookies from ~/.agent-reach/config.yaml)
  - Reddit     : rdt-cli (reads ~/.config/rdt-cli/credential.json)

Outputs a human-readable digest to stdout and a combined JSON next to --out
(default: scratch file). The qualitative X/Reddit sentiment is left for the
caller/LLM to synthesize; StockTwits sentiment is aggregated automatically.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()
TWITTER_BIN = HOME / ".local" / "bin" / "twitter.exe"
RDT_BIN = HOME / ".local" / "bin" / "rdt.exe"
AR_CONFIG = HOME / ".agent-reach" / "config.yaml"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _child_env() -> dict:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # inject twitter cookies from agent-reach config if present
    if AR_CONFIG.exists():
        for line in AR_CONFIG.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if k == "twitter_auth_token" and v:
                env["TWITTER_AUTH_TOKEN"] = v
            elif k == "twitter_ct0" and v:
                env["TWITTER_CT0"] = v
    return env


def _run(cmd: list[str], timeout: int = 40) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=_child_env())
        return r.stdout or ""
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] command failed: {' '.join(cmd[:2])} -> {e}", file=sys.stderr)
        return ""


# ── StockTwits ──────────────────────────────────────────────────────
def fetch_stocktwits(ticker: str) -> dict:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    out = {"platform": "stocktwits", "ok": False, "watchers": None,
           "sentiment": {}, "messages": []}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.load(resp)
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
        return out
    out["ok"] = True
    out["watchers"] = (data.get("symbol") or {}).get("watchlist_count")
    sent = Counter()
    for m in data.get("messages", []):
        basic = ((m.get("entities") or {}).get("sentiment") or {}).get("basic")
        sent[basic or "None"] += 1
        out["messages"].append({
            "time": m.get("created_at"),
            "author": (m.get("user") or {}).get("username"),
            "sentiment": basic,
            "text": " ".join((m.get("body") or "").split()),
        })
    out["sentiment"] = dict(sent)
    return out


# ── X / Twitter ─────────────────────────────────────────────────────
def fetch_twitter(query: str, since: str, limit: int) -> dict:
    out = {"platform": "x", "ok": False, "messages": []}
    if not TWITTER_BIN.exists():
        out["error"] = "twitter-cli not installed"
        return out
    raw = _run([str(TWITTER_BIN), "-c", "search", query, "--type", "latest",
                "--since", since, "-n", str(limit)])
    try:
        arr = json.loads(raw)
    except Exception:  # noqa: BLE001
        out["error"] = "unparseable output"
        out["raw"] = raw[:300]
        return out
    out["ok"] = True
    for m in arr:
        out["messages"].append({
            "time": m.get("time"),
            "author": m.get("author"),
            "likes": m.get("likes"),
            "rts": m.get("rts"),
            "text": " ".join((m.get("text") or "").split()),
        })
    return out


# ── Reddit ──────────────────────────────────────────────────────────
def fetch_reddit(query: str, limit: int, time_filter: str) -> dict:
    out = {"platform": "reddit", "ok": False, "messages": []}
    if not RDT_BIN.exists():
        out["error"] = "rdt-cli not installed"
        return out
    raw = _run([str(RDT_BIN), "search", query, "-s", "new", "-t", time_filter,
                "-n", str(limit), "--json"])
    try:
        # rdt --json emits a raw Reddit "Listing" object (sometimes with a
        # second JSON doc appended) -> decode only the first object.
        obj, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        node = obj.get("data", obj)
        if isinstance(node, dict) and "children" in node.get("data", {}):
            posts = node["data"]["children"]          # Listing -> children
        elif isinstance(node, dict) and node.get("kind") == "Listing":
            posts = node.get("data", {}).get("children", [])
        elif isinstance(node, list):
            posts = node                               # already flat
        else:
            posts = node.get("children", []) if isinstance(node, dict) else []
    except Exception as e:  # noqa: BLE001
        out["error"] = f"unparseable output: {e}"
        out["raw"] = raw[:300]
        return out
    out["ok"] = True
    for p in posts:
        d = p.get("data", p) if isinstance(p, dict) else {}
        out["messages"].append({
            "time": d.get("created_utc"),
            "subreddit": d.get("subreddit"),
            "author": d.get("author"),
            "score": d.get("score"),
            "num_comments": d.get("num_comments"),
            "title": d.get("title"),
            "text": " ".join((d.get("selftext") or "").split())[:400],
            "id": d.get("id"),
        })
    return out


def _fmt_ts(epoch):
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return str(epoch)


def digest(ticker, name, st, tw, rd):
    L = []
    L.append(f"\n{'='*64}\n  통합 소셜 리포트: ${ticker} ({name})\n{'='*64}")

    # StockTwits
    L.append("\n■ StockTwits  (네이티브 감성 태그)")
    if st["ok"]:
        s = st["sentiment"]
        bull, bear = s.get("Bullish", 0), s.get("Bearish", 0)
        tot = bull + bear
        ratio = f"  → 강세 {bull}/{tot} ({(bull/tot*100):.0f}%)" if tot else ""
        L.append(f"  watchlist 팔로워: {st['watchers']:,} | 최근 {len(st['messages'])}건")
        L.append(f"  감성: 🟢 Bullish {bull}  🔴 Bearish {bear}  ⚪ 중립 {s.get('None',0)}{ratio}")
        for m in st["messages"][:6]:
            tag = {"Bullish": "🟢", "Bearish": "🔴"}.get(m["sentiment"], "⚪")
            L.append(f"    {tag} {m['time'][5:16]} @{m['author']}: {m['text'][:110]}")
    else:
        L.append(f"  [실패] {st.get('error')}")

    # X
    L.append("\n■ X / Twitter  (최신순)")
    if tw["ok"]:
        L.append(f"  수집 {len(tw['messages'])}건")
        for m in tw["messages"][:8]:
            au = (m['author'] or '').lstrip('@')
            L.append(f"    {m['time']} @{au} (♥{m['likes']}): {m['text'][:110]}")
    else:
        L.append(f"  [실패] {tw.get('error')}")

    # Reddit
    L.append("\n■ Reddit  (이번 주 신규)")
    if rd["ok"]:
        L.append(f"  수집 {len(rd['messages'])}건")
        for m in rd["messages"][:8]:
            L.append(f"    {_fmt_ts(m['time'])} r/{m['subreddit']} (▲{m['score']} 💬{m['num_comments']}): {m['title'][:100]}")
    else:
        L.append(f"  [실패] {rd.get('error')}")

    L.append(f"\n{'='*64}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("name", nargs="?", default="", help="회사/키워드 (X·Reddit 검색용)")
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--out", default="", help="combined JSON 저장 경로")
    args = ap.parse_args()

    name = args.name or args.ticker
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    tf = "day" if args.days <= 1 else "week"
    x_query = f"${args.ticker} {name}".strip()

    print(f"수집 중… ${args.ticker} / '{name}' / since {since}", file=sys.stderr)
    st = fetch_stocktwits(args.ticker)
    tw = fetch_twitter(x_query, since, args.limit)
    rd = fetch_reddit(name, args.limit, tf)

    print(digest(args.ticker, name, st, tw, rd))

    combined = {"ticker": args.ticker, "name": name, "since": since,
                "stocktwits": st, "x": tw, "reddit": rd}
    out_path = args.out or os.path.join(
        os.environ.get("TEMP", "."), f"social_{args.ticker}.json")
    Path(out_path).write_text(json.dumps(combined, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\n[combined JSON] {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
