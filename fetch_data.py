#!/usr/bin/env python3
"""
fetch_data.py
Fetches Meta Ads data for all 5 Autocentro dealers and writes
one JSON file per dealer into the /data folder.
Runs via GitHub Actions every 24h. Token is stored in GitHub Secrets.
"""

import os
import json
import requests
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["META_ACCESS_TOKEN"]
API = "https://graph.facebook.com/v21.0"

DEALERS = [
    {"key": "nissan",   "id": "407938286956756",  "name": "Autocentro Nissan",           "color": "#C3002F"},
    {"key": "chrysler", "id": "766659464282943",  "name": "Autocentro Chrysler Dodge Jeep", "color": "#1877F2"},
    {"key": "mas",      "id": "850818032362895",  "name": "Autocentro Mas",              "color": "#f59e0b"},
    {"key": "guaynabo", "id": "1186750509063901", "name": "Autocentro Más Guaynabo",     "color": "#22c55e"},
    {"key": "toyota",   "id": "277757027036799",  "name": "Autocentro Toyota",           "color": "#EB0A1E"},
]

# Date ranges
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

FIELDS_ACCOUNT = (
    "amount_spent,impressions,reach,clicks,ctr,cpc,cpm,frequency,lead,"
    "video_thruplay_watched_actions,video_p25_watched_actions,"
    "video_p100_watched_actions,actions:page_engagement"
)

FIELDS_PLATFORM = (
    "amount_spent,impressions,reach,clicks,ctr,cpc,lead"
)

FIELDS_ADS = (
    "name,amount_spent,impressions,reach,clicks,ctr,cpc,frequency,lead,"
    "video_thruplay_watched_actions,video_p25_watched_actions,"
    "video_p100_watched_actions,objective,effective_status"
)

def api_get(path, params):
    params["access_token"] = TOKEN
    r = requests.get(f"{API}{path}", params=params, timeout=30)
    data = r.json()
    if "error" in data:
        print(f"  ⚠ API error on {path}: {data['error'].get('message','?')}")
        return None
    return data

def fetch_account_summary(acc_id, since, until):
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": FIELDS_ACCOUNT,
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 1,
    })
    if d and d.get("data"):
        return d["data"][0]
    return {}

def fetch_platform_breakdown(acc_id, since, until):
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": FIELDS_PLATFORM,
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

def fetch_top_ads(acc_id, since, until, limit=10):
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": FIELDS_ADS,
        "level": "ad",
        "time_range": json.dumps({"since": since, "until": until}),
        "sort": "amount_spent_descending",
        "limit": limit,
    })
    if d and d.get("data"):
        ads = []
        for a in d["data"]:
            ads.append({
                "name":      a.get("name", ""),
                "spend":     float(a.get("amount_spent", 0)),
                "imp":       int(a.get("impressions", 0)),
                "reach":     int(a.get("reach", 0)),
                "clicks":    int(a.get("clicks", 0)),
                "ctr":       float(a.get("ctr", 0)),
                "cpc":       float(a.get("cpc", 0)),
                "freq":      float(a.get("frequency", 0)),
                "leads":     int(a.get("lead", 0)),
                "thruplay":  int(a.get("video_thruplay_watched_actions", 0)),
                "views25":   int(a.get("video_p25_watched_actions", 0)),
                "views100":  int(a.get("video_p100_watched_actions", 0)),
                "objective": a.get("objective", ""),
                "status":    a.get("effective_status", ""),
            })
        return ads
    return []

def normalize_summary(raw):
    if not raw:
        return {}
    return {
        "spend":     float(raw.get("amount_spent", 0)),
        "imp":       int(raw.get("impressions", 0)),
        "reach":     int(raw.get("reach", 0)),
        "clicks":    int(raw.get("clicks", 0)),
        "ctr":       float(raw.get("ctr", 0)),
        "cpc":       float(raw.get("cpc", 0)),
        "cpm":       float(raw.get("cpm", 0)),
        "freq":      float(raw.get("frequency", 0)),
        "leads":     int(raw.get("lead", 0)),
        "thruplay":  int(raw.get("video_thruplay_watched_actions", 0)),
        "views25":   int(raw.get("video_p25_watched_actions", 0)),
        "views100":  int(raw.get("video_p100_watched_actions", 0)),
    }

def main():
    os.makedirs("data", exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today = str(datetime.now(timezone.utc).date())

    for dealer in DEALERS:
        key  = dealer["key"]
        aid  = dealer["id"]
        name = dealer["name"]
        print(f"\n→ Fetching {name} (act_{aid})")

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
            summary_raw = fetch_account_summary(aid, since, until)
            summary     = normalize_summary(summary_raw)
            platforms   = fetch_platform_breakdown(aid, since, until)
            ads         = fetch_top_ads(aid, since, until, limit=10)

            payload["ranges"][rng_key] = {
                "since":     since,
                "until":     until,
                "summary":   summary,
                "platforms": platforms,
                "ads":       ads,
            }

        out_path = f"data/{key}_data.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved {out_path}")

    print("\n✅ All dealers done.")

if __name__ == "__main__":
    main()
