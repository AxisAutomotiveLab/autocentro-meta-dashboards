#!/usr/bin/env python3
"""
fetch_data.py — Autocentro PR Meta Ads + Organic fetcher
Runs via GitHub Actions every 24h. Token in GitHub Secrets as META_ACCESS_TOKEN.
Permissions: ads_read, ads_management, business_management,
             pages_read_engagement, pages_show_list
"""

import os, json, time, requests
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
API   = "https://graph.facebook.com/v21.0"

DEALERS = [
    {"key":"nissan",   "ad_id":"407938286956756",  "page_id":"734231516710477",  "name":"Autocentro Nissan",              "color":"#C3002F"},
    {"key":"chrysler", "ad_id":"766659464282943",  "page_id":"267711843253862",  "name":"Autocentro Chrysler Dodge Jeep", "color":"#1877F2"},
    {"key":"mas",      "ad_id":"850818032362895",  "page_id":"457461994795559",  "name":"Autocentro Mas",                 "color":"#f59e0b"},
    {"key":"guaynabo", "ad_id":"1186750509063901", "page_id":"371177979415117",  "name":"Autocentro Más Guaynabo",        "color":"#22c55e"},
    {"key":"toyota",   "ad_id":"277757027036799",  "page_id":"108458989181126",  "name":"Autocentro Toyota",              "color":"#EB0A1E"},
]

def date_range(days_back):
    today = datetime.now(timezone.utc).date()
    return str(today - timedelta(days=days_back-1)), str(today)

RANGES = {
    "last_7d":  date_range(7),
    "last_14d": date_range(14),
    "last_30d": date_range(30),
    "last_90d": date_range(90),
}

PAGE_TOKENS = {}   # page_id → page_access_token
PAGE_NAMES  = {}   # page_id → page_name

# ── core ───────────────────────────────────────────────────────────────────────

def api_get(path, params, token=None, retries=2):
    params["access_token"] = token or TOKEN
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{API}{path}", params=params, timeout=30)
            d = r.json()
            if "error" in d:
                err = d["error"]
                code = err.get("code", 0)
                print(f"    ⚠ API error [{code}] {err.get('message','?')[:120]}")
                if code == 4 and attempt < retries:
                    print(f"    ↻ Rate limit — waiting 15s (attempt {attempt+1})")
                    time.sleep(15); continue
                return None
            return d
        except Exception as e:
            print(f"    ⚠ Request failed: {e}")
            if attempt < retries: time.sleep(5)
    return None

def safe_int(v):
    try: return int(float(str(v).replace(",","")))
    except: return 0

def safe_float(v):
    try: return float(str(v).replace(",",""))
    except: return 0.0

def extract_action(actions, *types):
    if not isinstance(actions, list): return 0
    for item in actions:
        if item.get("action_type") in types:
            return safe_int(item.get("value", 0))
    return 0

def extract_video(v):
    if not v: return 0
    if isinstance(v, (int,float,str)): return safe_int(v)
    if isinstance(v, list) and v: return safe_int(v[0].get("value",0))
    return 0

# ── page tokens ────────────────────────────────────────────────────────────────

def load_page_tokens():
    print("\n→ Loading Page Access Tokens via /me/accounts...")
    d = api_get("/me/accounts", {"fields":"id,name,access_token", "limit":25})
    if not d or not d.get("data"):
        print("  ⚠ Could not fetch page tokens")
        return False
    for page in d["data"]:
        pid = page.get("id","")
        tok = page.get("access_token","")
        nm  = page.get("name","")
        if pid and tok:
            PAGE_TOKENS[pid] = tok
            PAGE_NAMES[pid]  = nm
            print(f"  ✅ {nm} ({pid})")
    print(f"  ✓ {len(PAGE_TOKENS)} page tokens loaded")
    return len(PAGE_TOKENS) > 0

# ── paid fetchers ──────────────────────────────────────────────────────────────

def fetch_summary(acc_id, since, until):
    fields = ("spend,impressions,reach,clicks,ctr,cpc,cpm,frequency,"
              "actions,video_thruplay_watched_actions,"
              "video_p25_watched_actions,video_p100_watched_actions")
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": fields,
        "time_range": json.dumps({"since":since,"until":until}),
        "limit": 1,
    })
    if d and d.get("data"):
        r = d["data"][0]
        actions = r.get("actions",[])
        leads = extract_action(actions,
            "lead","onsite_conversion.lead_grouped",
            "leadgen.other","onsite_conversion.total_messaging_connection")
        return {
            "spend":    safe_float(r.get("spend",0)),
            "imp":      safe_int(r.get("impressions",0)),
            "reach":    safe_int(r.get("reach",0)),
            "clicks":   safe_int(r.get("clicks",0)),
            "ctr":      safe_float(r.get("ctr",0)),
            "cpc":      safe_float(r.get("cpc",0)),
            "cpm":      safe_float(r.get("cpm",0)),
            "freq":     safe_float(r.get("frequency",0)),
            "leads":    leads,
            "thruplay": extract_video(r.get("video_thruplay_watched_actions")),
            "views25":  extract_video(r.get("video_p25_watched_actions")),
            "views100": extract_video(r.get("video_p100_watched_actions")),
        }
    return {}

def fetch_platforms(acc_id, since, until):
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": "spend,impressions,reach,clicks,ctr,cpc,actions",
        "breakdowns": "publisher_platform",
        "time_range": json.dumps({"since":since,"until":until}),
        "limit": 10,
    })
    if d and d.get("data"):
        result = {}
        for row in d["data"]:
            p = row.get("publisher_platform","unknown")
            actions = row.get("actions",[])
            leads = extract_action(actions,
                "lead","onsite_conversion.lead_grouped","leadgen.other")
            result[p] = {
                "spend":  safe_float(row.get("spend",0)),
                "imp":    safe_int(row.get("impressions",0)),
                "reach":  safe_int(row.get("reach",0)),
                "clicks": safe_int(row.get("clicks",0)),
                "ctr":    safe_float(row.get("ctr",0)),
                "cpc":    safe_float(row.get("cpc",0)),
                "leads":  leads,
            }
        return result
    return {}

def fetch_ads(acc_id, since, until, limit=75):
    fields = ("ad_name,spend,impressions,reach,clicks,ctr,cpc,frequency,"
              "actions,video_thruplay_watched_actions,"
              "video_p25_watched_actions,video_p100_watched_actions")
    d = api_get(f"/act_{acc_id}/insights", {
        "fields": fields,
        "level": "ad",
        "time_range": json.dumps({"since":since,"until":until}),
        "limit": limit,
    })
    if d and d.get("data"):
        ads = []
        for a in d["data"]:
            actions = a.get("actions",[])
            leads = extract_action(actions,
                "lead","onsite_conversion.lead_grouped","leadgen.other")
            ads.append({
                "name":     a.get("ad_name", a.get("name","")),
                "spend":    safe_float(a.get("spend",0)),
                "imp":      safe_int(a.get("impressions",0)),
                "reach":    safe_int(a.get("reach",0)),
                "clicks":   safe_int(a.get("clicks",0)),
                "ctr":      safe_float(a.get("ctr",0)),
                "cpc":      safe_float(a.get("cpc",0)),
                "freq":     safe_float(a.get("frequency",0)),
                "leads":    leads,
                "thruplay": extract_video(a.get("video_thruplay_watched_actions")),
                "views25":  extract_video(a.get("video_p25_watched_actions")),
                "views100": extract_video(a.get("video_p100_watched_actions")),
            })
        ads.sort(key=lambda x: x["spend"], reverse=True)
        return ads
    return []

# ── organic via /me/feed filtered by page ─────────────────────────────────────

def fetch_organic_posts(page_id, page_token, since, until, limit=25):
    """
    Fetch posts from a specific page using the Page Access Token + /PAGE_ID/feed.
    Using page token with /PAGE_ID/feed works without Page Public Content Access.
    Falls back to basic metrics if insights endpoint is restricted.
    """
    fields = ("id,message,story,created_time,full_picture,permalink_url,"
              "shares,likes.summary(true),comments.summary(true),"
              "attachments{media_type,type},insights.metric("
              "post_impressions,post_impressions_organic,"
              "post_impressions_paid,post_engaged_users,post_video_views)"
              "{name,values}")

    d = api_get(f"/{page_id}/feed", {
        "fields": fields,
        "since":  since,
        "until":  until,
        "limit":  limit,
    }, token=page_token)

    if not d or not d.get("data"):
        print(f"    ℹ No posts found")
        return []

    posts_raw = d["data"]
    print(f"    → {len(posts_raw)} posts found")

    posts = []
    for p in posts_raw:
        post_id  = p.get("id","")
        likes    = safe_int(p.get("likes",{}).get("summary",{}).get("total_count",0))
        comments = safe_int(p.get("comments",{}).get("summary",{}).get("total_count",0))
        shares   = safe_int(p.get("shares",{}).get("count",0))
        attach   = p.get("attachments",{}).get("data",[{}])
        mtype    = attach[0].get("media_type", attach[0].get("type","photo")) if attach else "photo"
        caption  = p.get("message", p.get("story",""))[:120]

        # Parse inline insights (fetched together to avoid extra API calls)
        ins_data = p.get("insights",{}).get("data",[])
        ins = {}
        for m in ins_data:
            vals = m.get("values",[])
            ins[m["name"]] = safe_int(vals[-1].get("value",0) if vals else 0)

        posts.append({
            "id":                  post_id,
            "caption":             caption,
            "created_time":        p.get("created_time",""),
            "permalink":           p.get("permalink_url",""),
            "thumbnail":           p.get("full_picture",""),
            "media_type":          mtype,
            "likes":               likes,
            "comments":            comments,
            "shares":              shares,
            "impressions":         ins.get("post_impressions", 0),
            "impressions_organic": ins.get("post_impressions_organic", 0),
            "impressions_paid":    ins.get("post_impressions_paid", 0),
            "engaged_users":       ins.get("post_engaged_users", 0),
            "video_views":         ins.get("post_video_views", 0),
        })

    posts.sort(key=lambda x: x["impressions"], reverse=True)
    print(f"    ✓ {len(posts)} posts processed")
    return posts[:10]

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("  Autocentro PR — Meta Ads + Organic Data Fetch")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*60)

    if not TOKEN:
        print("❌ META_ACCESS_TOKEN is empty"); exit(1)
    print(f"  Token prefix: {TOKEN[:12]}...")

    d = api_get("/me", {"fields":"id,name"})
    if not d:
        print("❌ Token invalid"); exit(1)
    print(f"  ✅ Token valid — user: {d.get('name', d.get('id','?'))}")

    load_page_tokens()

    os.makedirs("data", exist_ok=True)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today = str(datetime.now(timezone.utc).date())

    for dealer in DEALERS:
        key, aid, pid = dealer["key"], dealer["ad_id"], dealer["page_id"]
        name = dealer["name"]
        page_token = PAGE_TOKENS.get(pid)

        print(f"\n{'='*60}")
        print(f"→ {name}")
        print(f"  Ad Account: act_{aid} | Page: {pid}")
        print(f"  Page token: {'✅ available' if page_token else '⚠ not found'}")

        payload = {
            "meta": {
                "dealer_key":  key,
                "dealer_name": name,
                "account_id":  aid,
                "page_id":     pid,
                "color":       dealer["color"],
                "fetched_at":  fetched_at,
                "data_date":   today,
            },
            "ranges": {},
            "organic": {},
        }

        # ── Paid ───────────────────────────────────────────────
        for rk, (since, until) in RANGES.items():
            print(f"\n  [PAID] {rk} ({since} → {until})")
            summary   = fetch_summary(aid, since, until)
            platforms = fetch_platforms(aid, since, until)
            ads       = fetch_ads(aid, since, until)
            if summary:
                print(f"    ✓ spend:${round(summary.get('spend',0)):,} | leads:{summary.get('leads',0)} | thruplay:{summary.get('thruplay',0):,} | ads:{len(ads)}")
            payload["ranges"][rk] = {
                "since":since,"until":until,
                "summary":summary,"platforms":platforms,"ads":ads,
            }
            time.sleep(0.5)

        # ── Organic via /PAGE_ID/feed + inline insights ────────
        for rk, (since, until) in RANGES.items():
            print(f"\n  [ORGANIC] {rk} ({since} → {until})")
            if page_token:
                posts = fetch_organic_posts(pid, page_token, since, until, limit=25)
            else:
                posts = []
                print(f"    ⚠ No page token available")
            payload["organic"][rk] = {"since":since,"until":until,"posts":posts}
            time.sleep(1)

        out = f"data/{key}_data.json"
        with open(out,"w",encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n  ✓ Saved {out}")
        time.sleep(2)

    print("\n"+"="*60)
    print("✅ All dealers done.")

if __name__ == "__main__":
    main()
