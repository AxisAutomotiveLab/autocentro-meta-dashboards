#!/usr/bin/env python3
"""
fetch_data.py — Autocentro PR Meta Ads fetcher
Runs via GitHub Actions every 24h. Token in GitHub Secrets as META_ACCESS_TOKEN.
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
            print(f"    ⚠ API error [{err.get('code','?')}] {err.get('message','?')}")
            return None
        return data
    except Exception as e:
        print(f"    ⚠ Request failed: {e}")
        return None

def verify_token():
    print("→ Verifying token...")
    d = api_get("/me", {"fields": "id,name"})
    if d:
        print(f"  ✅ Token valid — user: {d.get('name', d.get('id', '?'))}")
        return True
    print("  ❌ Token verification failed")
    return False

def safe_int(v):
    try: return int(float(str(v).replace(',', '')))
    except: return 0

def safe_float(v):
    try: return float(str(v).replace(',', ''))
    except: return 0.0

def extract_action(actions_list, action_type):
    """
    Meta API returns actions as: [{"action_type": "lead", "value": "42"}, ...]
    This extracts the value for a specific action_type.
    """
    if not actions_list or not isinstance(actions_list, list):
        return 0
    for item in actions_list:
        if item.get("action_type") == action_type:
            return safe_int(item.get("value", 0))
    return 0

def extract_video(video_list):
    """
    Video metrics like video_thruplay_watched_actions come as:
    [{"action_type": "video_thruplay_watched_actions", "value": "500"}]
    or just a plain integer/string in some API versions.
    """
    if not video_list:
        return 0
    if isinstance(video_list, (int, float, str)):
        return safe_int(video_list)
    if isinstance(video_list, list) and len(video_list) > 0:
        return safe_int(video_list[0].get("value", 0))
    return 0

def fetch_summary(acc_id, since, until):
    """
    Account-level summary.
    leads come from actions array: action_type='lead' or 'onsite_conversion.lead_grouped'
    video comes from video_thruplay_watched_actions (can be list or int)
    """
    fields = (
        "spend,impressions,reach,clicks,ctr,cpc,cpm,frequency,"
        "actions,video_thruplay_watched_actions,video_p25_watched_actions,video_p100_watched_actions"
    )
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": fields,
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 1,
    })
    if d and d.get("data"):
        r = d["data"][0]
        actions = r.get("actions", [])

        # Leads: try multiple action types Meta uses for leads
        leads = (
            extract_action(actions, "lead") or
            extract_action(actions, "onsite_conversion.lead_grouped") or
            extract_action(actions, "leadgen.other") or
            safe_int(r.get("lead", 0))
        )

        thruplay = extract_video(r.get("video_thruplay_watched_actions"))
        views25  = extract_video(r.get("video_p25_watched_actions"))
        views100 = extract_video(r.get("video_p100_watched_actions"))

        result = {
            "spend":    safe_float(r.get("spend", 0)),
            "imp":      safe_int(r.get("impressions", 0)),
            "reach":    safe_int(r.get("reach", 0)),
            "clicks":   safe_int(r.get("clicks", 0)),
            "ctr":      safe_float(r.get("ctr", 0)),
            "cpc":      safe_float(r.get("cpc", 0)),
            "cpm":      safe_float(r.get("cpm", 0)),
            "freq":     safe_float(r.get("frequency", 0)),
            "leads":    leads,
            "thruplay": thruplay,
            "views25":  views25,
            "views100": views100,
        }

        # Debug: show raw actions so we can see what action types exist
        if actions:
            action_types = [a.get("action_type") for a in actions]
            print(f"    ℹ action_types available: {action_types}")

        return result
    return {}

def fetch_platforms(acc_id, since, until):
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": "spend,impressions,reach,clicks,ctr,cpc,actions",
        "breakdowns": "publisher_platform",
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": 10,
    })
    if d and d.get("data"):
        result = {}
        for row in d["data"]:
            p = row.get("publisher_platform", "unknown")
            actions = row.get("actions", [])
            leads = (
                extract_action(actions, "lead") or
                extract_action(actions, "onsite_conversion.lead_grouped") or
                extract_action(actions, "leadgen.other")
            )
            result[p] = {
                "spend":  safe_float(row.get("spend", 0)),
                "imp":    safe_int(row.get("impressions", 0)),
                "reach":  safe_int(row.get("reach", 0)),
                "clicks": safe_int(row.get("clicks", 0)),
                "ctr":    safe_float(row.get("ctr", 0)),
                "cpc":    safe_float(row.get("cpc", 0)),
                "leads":  leads,
            }
        return result
    return {}

def fetch_ads(acc_id, since, until, limit=10):
    fields = (
        "ad_name,spend,impressions,reach,clicks,ctr,cpc,frequency,"
        "actions,video_thruplay_watched_actions,video_p25_watched_actions,video_p100_watched_actions"
    )
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": fields,
        "level": "ad",
        "time_range": json.dumps({"since": since, "until": until}),
        "limit": limit,
    })
    if d and d.get("data"):
        ads = []
        for a in d["data"]:
            actions = a.get("actions", [])
            leads = (
                extract_action(actions, "lead") or
                extract_action(actions, "onsite_conversion.lead_grouped") or
                extract_action(actions, "leadgen.other")
            )
            thruplay = extract_video(a.get("video_thruplay_watched_actions"))
            views25  = extract_video(a.get("video_p25_watched_actions"))
            views100 = extract_video(a.get("video_p100_watched_actions"))

            ads.append({
                "name":     a.get("ad_name", a.get("name", "")),
                "spend":    safe_float(a.get("spend", 0)),
                "imp":      safe_int(a.get("impressions", 0)),
                "reach":    safe_int(a.get("reach", 0)),
                "clicks":   safe_int(a.get("clicks", 0)),
                "ctr":      safe_float(a.get("ctr", 0)),
                "cpc":      safe_float(a.get("cpc", 0)),
                "freq":     safe_float(a.get("frequency", 0)),
                "leads":    leads,
                "thruplay": thruplay,
                "views25":  views25,
                "views100": views100,
            })
        ads.sort(key=lambda x: x["spend"], reverse=True)
        return ads
    return []

def main():
    print("=" * 55)
    print("  Autocentro PR — Meta Ads Data Fetch")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 55)

    if not TOKEN:
        print("❌ META_ACCESS_TOKEN is empty — check GitHub Secrets")
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
                print(f"    ✓ spend: ${round(summary.get('spend',0)):,} | leads: {summary.get('leads',0)} | thruplay: {summary.get('thruplay',0):,}")
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
