#!/usr/bin/env python3
"""
fetch_data.py — Autocentro PR Meta Ads fetcher
Runs via GitHub Actions every 24h. Token stored in GitHub Secrets as META_ACCESS_TOKEN.
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
API = "https://graph.facebook.com/v21.0"

DEALERS = [
    {"key": "nissan",   "id": "407938286956756",  "name": "Autocentro Nissan",              "color": "#C3002F"},
    {"key": "chrysler", "id": "766659464282943",  "name": "Autocentro Chrysler Dodge Jeep", "color": "#1877F2"},
    {"key": "mas",      "id": "850818032362895",  "name": "Autocentro Mas",                 "color": "#f59e0b"},
    {"key": "guaynabo", "id": "1186750509063901", "name": "Autocentro Más Guaynabo",        "color": "#22c55e"},
    {"key": "toyota",   "id": "277757027036799",  "name": "Autocentro Toyota",              "color": "#EB0A1E"},
]

def date_range(days_back):
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=days_back - 1)
    return str(since), str(today)

RANGES = {
    "last_7d":  date_range(7),
    "last_14d": date_range(14),
    "last_30d": date_range(30),
    "last_90d": date_range(90),
}

def api_get(path, params):
    params["access_token"] = TOKEN
    try:
        r = requests.get(f"{API}{path}", params=params, timeout=30)
        data = r.json()
        if "error" in data:
            err = data["error"]
            print(f"  ⚠ API error [{err.get('code','?')}] {err.get('message','?')}")
            if err.get("code") in [190, 102]:
                print("  ❌ TOKEN EXPIRADO o inválido — regenera en Graph Explorer")
            return None
        return data
    except Exception as e:
        print(f"  ⚠ Request failed: {e}")
        return None

def verify_token():
    print("→ Verifying token...")
    d = api_get("/me", {"fields": "id,name"})
    if d:
        print(f"  ✅ Token valid — user: {d.get('name', d.get('id', '?'))}")
        return True
    print("  ❌ Token verification failed")
    return False

def fetch_summary(acc_id, since, until):
    fields = (
        "amount_spent,impressions,reach,clicks,ctr,cpc,cpm,frequency,lead,"
        "video_thruplay_watched_actions,video_p25_watched_actions,video_p100_watched_actions"
    )
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": fields,
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 1,
    })
    if d and d.get("data"):
        r = d["data"][0]
        return {
            "spend":    float(r.get("amount_spent", 0)),
            "imp":      int(r.get("impressions", 0)),
            "reach":    int(r.get("reach", 0)),
            "clicks":   int(r.get("clicks", 0)),
            "ctr":      float(r.get("ctr", 0)),
            "cpc":      float(r.get("cpc", 0)),
            "cpm":      float(r.get("cpm", 0)),
            "freq":     float(r.get("frequency", 0)),
            "leads":    int(r.get("lead", 0)),
            "thruplay": int(r.get("video_thruplay_watched_actions", 0)),
            "views25":  int(r.get("video_p25_watched_actions", 0)),
            "views100": int(r.get("video_p100_watched_actions", 0)),
        }
    if d and not d.get("data"):
        print(f"    ℹ No data returned for this period (account may have no spend)")
    return {}

def fetch_platforms(acc_id, since, until):
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": "amount_spent,impressions,reach,clicks,ctr,cpc,lead",
        "breakdowns": "publisher_platform",
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 10,
    })
    if d and d.get("data"):
        result = {}
        for row in d["data"]:
            p = row.get("publisher_platform", "unknown")
            result[p] = {
                "spend":  float(row.get("amount_spent", 0)),
                "imp":    int(row.get("impressions", 0)),
                "reach":  int(row.get("reach", 0)),
                "clicks": int(row.get("clicks", 0)),
                "ctr":    float(row.get("ctr", 0)),
                "cpc":    float(row.get("cpc", 0)),
                "leads":  int(row.get("lead", 0)),
            }
        return result
    return {}

def fetch_ads(acc_id, since, until, limit=10):
    fields = (
        "name,amount_spent,impressions,reach,clicks,ctr,cpc,frequency,lead,"
        "video_thruplay_watched_actions,video_p25_watched_actions,"
        "video_p100_watched_actions,objective,effective_status"
    )
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": fields,
        "level": "ad",
        "time_range": json.dumps({"since": since, "until": until}),
        "sort": "amount_spent_descending",
        "limit": limit,
    })
    if d and d.get("data"):
        ads = []
        for a in d["data"]:
            ads.append({
                "name":     a.get("name", ""),
                "spend":    float(a.get("amount_spent", 0)),
                "imp":      int(a.get("impressions", 0)),
                "reach":    int(a.get("reach", 0)),
                "clicks":   int(a.get("clicks", 0)),
                "ctr":      float(a.get("ctr", 0)),
                "cpc":      float(a.get("cpc", 0)),
                "freq":     float(a.get("frequency", 0)),
                "leads":    int(a.get("lead", 0)),
                "thruplay": int(a.get("video_thruplay_watched_actions", 0)),
                "views25":  int(a.get("video_p25_watched_actions", 0)),
                "views100": int(a.get("video_p100_watched_actions", 0)),
                "objective":a.get("objective", ""),
                "status":   a.get("effective_status", ""),
            })
        return ads
    return []

def main():
    print("=" * 55)
    print("  Autocentro PR — Meta Ads Data Fetch")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 55)

    if not TOKEN:
        print("❌ META_ACCESS_TOKEN secret is empty or not set!")
        print("   Go to repo Settings → Secrets → add META_ACCESS_TOKEN")
        exit(1)

    print(f"  Token prefix: {TOKEN[:12]}...")

    if not verify_token():
        exit(1)

    os.makedirs("data", exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today = str(datetime.now(timezone.utc).date())

    for dealer in DEALERS:
        key, aid, name = dealer["key"], dealer["id"], dealer["name"]
        print(f"\n→ {name} (act_{aid})")

        payload = {
            "meta": {
                "dealer_key":  key,
                "dealer_name": name,
                "account_id":  aid,
                "color":       dealer["color"],
                "fetched_at":  fetched_at,
                "data_date":   today,
            },
            "ranges": {},
        }

        for rng_key, (since, until) in RANGES.items():
            print(f"  • {rng_key} ({since} → {until})")
            summary   = fetch_summary(aid, since, until)
            platforms = fetch_platforms(aid, since, until)
            ads       = fetch_ads(aid, since, until, limit=10)
            if summary:
                print(f"    → spend: ${round(summary.get('spend',0))} | leads: {summary.get('leads',0)} | imp: {summary.get('imp',0):,}")
            payload["ranges"][rng_key] = {
                "since": since, "until": until,
                "summary": summary, "platforms": platforms, "ads": ads,
            }

        out = f"data/{key}_data.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved {out}")

    print("\n✅ All dealers done.")

if __name__ == "__main__":
    main()
