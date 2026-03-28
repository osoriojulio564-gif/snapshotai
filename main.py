SnapshotAI — Website Intelligence Report Generator
FastAPI app: scrapes a URL, calls Claude, generates a branded PDF.
Deploy to Render as a Web Service.
“””

import os
import io
import re
import time
import json
import hashlib
import urllib.parse
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

from report_generator import generate_pdf_report

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title=“SnapshotAI Report Generator”, version=“1.0.0”)

app.add_middleware(
CORSMiddleware,
allow_origins=[”*”],   # tighten to your domain in production
allow_methods=[”*”],
allow_headers=[”*”],
)

# ── Config ─────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get(“ANTHROPIC_API_KEY”, “”)
REPORTS_DIR = “/tmp/reports”
os.makedirs(REPORTS_DIR, exist_ok=True)

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Models ─────────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
url: str
email: Optional[str] = None   # set after payment

class ScanResult(BaseModel):
report_id: str
score: int
preview_issues: list
status: str

# ── Scraper ────────────────────────────────────────────────────────────────────

def scrape_website(url: str) -> dict:
“””
Fetch the page and extract every signal we can without JS execution.
Returns a structured dict of raw observations.
“””
if not url.startswith(“http”):
url = “https://” + url

```
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

start = time.time()
try:
    resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    load_time_ms = int((time.time() - start) * 1000)
except requests.exceptions.SSLError:
    resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True, verify=False)
    load_time_ms = int((time.time() - start) * 1000)

soup = BeautifulSoup(resp.text, "html.parser")
final_url = resp.url
parsed = urllib.parse.urlparse(final_url)
domain = parsed.netloc

# ── Meta & SEO ─────────────────────────────────────────────────────────────
title_tag     = soup.find("title")
meta_desc     = soup.find("meta", attrs={"name": "description"})
meta_robots   = soup.find("meta", attrs={"name": "robots"})
canonical     = soup.find("link", rel="canonical")
og_title      = soup.find("meta", property="og:title")
og_desc       = soup.find("meta", property="og:description")
og_image      = soup.find("meta", property="og:image")
twitter_card  = soup.find("meta", attrs={"name": "twitter:card"})
viewport      = soup.find("meta", attrs={"name": "viewport"})
charset       = soup.find("meta", attrs={"charset": True}) or soup.find("meta", attrs={"http-equiv": "Content-Type"})
lang_attr     = soup.find("html").get("lang", "") if soup.find("html") else ""
structured_data = soup.find_all("script", type="application/ld+json")

# ── Headings ───────────────────────────────────────────────────────────────
h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
h3s = [h.get_text(strip=True) for h in soup.find_all("h3")]

# ── Content ────────────────────────────────────────────────────────────────
body_text = soup.get_text(separator=" ", strip=True)
word_count = len(body_text.split())
paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]

# ── Images ─────────────────────────────────────────────────────────────────
images = soup.find_all("img")
images_without_alt = [img.get("src", "")[:80] for img in images if not img.get("alt")]
images_with_alt = len(images) - len(images_without_alt)

# ── Links ──────────────────────────────────────────────────────────────────
all_links     = soup.find_all("a", href=True)
internal_links = [a["href"] for a in all_links if domain in a["href"] or a["href"].startswith("/")]
external_links = [a["href"] for a in all_links if a["href"].startswith("http") and domain not in a["href"]]
broken_anchors = [a["href"] for a in all_links if a["href"] in ("#", "javascript:void(0)", "javascript:;")]

# ── CTAs & Forms ───────────────────────────────────────────────────────────
buttons       = soup.find_all("button")
cta_texts     = [b.get_text(strip=True) for b in buttons if b.get_text(strip=True)]
forms         = soup.find_all("form")
input_fields  = soup.find_all("input")

# ── Trust signals ──────────────────────────────────────────────────────────
https_active  = final_url.startswith("https://")
has_phone     = bool(re.search(r'\+?[\d\s\-\(\)]{7,}', body_text))
has_address   = bool(re.search(r'\d+\s+\w+\s+(St|Ave|Rd|Blvd|Dr|Lane|Way|Pl|Court)', body_text, re.I))
privacy_link  = any("privacy" in a.get("href", "").lower() for a in all_links)
terms_link    = any("terms" in a.get("href", "").lower() for a in all_links)
social_links  = [a["href"] for a in all_links if any(s in a["href"] for s in ["facebook.com", "twitter.com", "instagram.com", "linkedin.com", "tiktok.com", "youtube.com"])]
review_keywords = bool(re.search(r'review|testimonial|stars|rated|trustpilot|google review', body_text, re.I))

# ── Performance signals (from HTML only) ──────────────────────────────────
scripts       = soup.find_all("script", src=True)
stylesheets   = soup.find_all("link", rel="stylesheet")
inline_styles = soup.find_all("style")
lazy_images   = [img for img in images if img.get("loading") == "lazy"]
html_size_kb  = round(len(resp.text) / 1024, 1)

# ── Mobile signals ────────────────────────────────────────────────────────
has_viewport  = viewport is not None
viewport_content = viewport.get("content", "") if viewport else ""
responsive_css = "media" in resp.text.lower()
font_sizes    = re.findall(r'font-size:\s*([\d.]+)(px|rem|em)', resp.text)

# ── Favicon ───────────────────────────────────────────────────────────────
favicon = soup.find("link", rel=lambda r: r and "icon" in r)

return {
    "url": final_url,
    "domain": domain,
    "status_code": resp.status_code,
    "load_time_ms": load_time_ms,
    "html_size_kb": html_size_kb,
    "https": https_active,

    # SEO
    "title": title_tag.get_text(strip=True) if title_tag else None,
    "title_length": len(title_tag.get_text(strip=True)) if title_tag else 0,
    "meta_description": meta_desc.get("content", "").strip() if meta_desc else None,
    "meta_desc_length": len(meta_desc.get("content", "")) if meta_desc else 0,
    "canonical_url": canonical.get("href") if canonical else None,
    "lang": lang_attr,
    "charset_declared": charset is not None,
    "robots_meta": meta_robots.get("content", "") if meta_robots else None,
    "structured_data_count": len(structured_data),
    "structured_data_raw": [s.string for s in structured_data[:3] if s.string],

    # Social meta
    "og_title": og_title.get("content") if og_title else None,
    "og_description": og_desc.get("content") if og_desc else None,
    "og_image": og_image.get("content") if og_image else None,
    "twitter_card": twitter_card.get("content") if twitter_card else None,

    # Headings
    "h1_count": len(h1s),
    "h1_texts": h1s[:5],
    "h2_count": len(h2s),
    "h2_texts": h2s[:10],
    "h3_count": len(h3s),

    # Content
    "word_count": word_count,
    "paragraph_count": len(paragraphs),
    "first_paragraphs": paragraphs[:4],

    # Images
    "image_count": len(images),
    "images_without_alt": len(images_without_alt),
    "images_with_alt": images_with_alt,
    "lazy_images": len(lazy_images),

    # Links
    "internal_link_count": len(internal_links),
    "external_link_count": len(external_links),
    "broken_anchor_count": len(broken_anchors),

    # CTAs & Forms
    "button_count": len(buttons),
    "cta_texts": cta_texts[:10],
    "form_count": len(forms),
    "input_count": len(input_fields),

    # Trust
    "has_phone": has_phone,
    "has_address": has_address,
    "has_privacy_link": privacy_link,
    "has_terms_link": terms_link,
    "social_links": social_links[:8],
    "has_reviews_testimonials": review_keywords,
    "has_favicon": favicon is not None,

    # Performance (HTML proxy)
    "external_scripts_count": len(scripts),
    "stylesheets_count": len(stylesheets),
    "inline_styles_count": len(inline_styles),

    # Mobile
    "has_viewport_meta": has_viewport,
    "viewport_content": viewport_content,
    "responsive_css_detected": responsive_css,
}
```

# ── Deterministic Revenue Calculator ──────────────────────────────────────────

def calculate_revenue_lost(scraped: dict, score: int) -> str:
“””
Calculate estimated monthly revenue lost deterministically from scraped data.
Same inputs ALWAYS produce the same output — no AI randomness.
Formula based on industry CRO benchmarks.
“””
# Seed random with URL hash so same URL = same number every time
url_seed = int(hashlib.md5(scraped[“url”].encode()).hexdigest()[:8], 16)
import random
rng = random.Random(url_seed)

```
# Base penalty: lower score = more revenue lost
score_penalty = max(0, (70 - score)) / 70  # 0 to 1 scale

# Estimate monthly visitors based on site signals
has_social     = len(scraped.get("social_links", [])) > 0
has_structured = scraped.get("structured_data_count", 0) > 0
word_count     = scraped.get("word_count", 0)
has_meta       = scraped.get("meta_description") is not None

# Visitor estimate bucket
if word_count > 2000 and has_structured and has_social:
    base_visitors = rng.randint(3000, 8000)
elif word_count > 800 and has_meta:
    base_visitors = rng.randint(800, 3000)
else:
    base_visitors = rng.randint(200, 800)

# Industry avg conversion rate 2-4%, avg order $80-$200
conversion_rate = rng.uniform(0.02, 0.04)
avg_order       = rng.randint(80, 200)

# Revenue lost = visitors * conversion_rate * avg_order * penalty
lost_low  = int(base_visitors * conversion_rate * avg_order * score_penalty * 0.8)
lost_high = int(base_visitors * conversion_rate * avg_order * score_penalty * 1.3)

# Round to clean numbers
lost_low  = max(200, round(lost_low  / 100) * 100)
lost_high = max(400, round(lost_high / 100) * 100)

return f"${lost_low:,}–${lost_high:,}/mo"
```

# ── Claude Analysis ────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = “””
You are a senior digital marketing consultant and technical SEO expert.
You have just received raw scraped data from a website audit tool.

Your job is to produce a PROFESSIONAL, FORMAL, DEEPLY ANALYTICAL website intelligence report.
Be specific, data-driven, and ruthlessly honest. Do NOT be generic.

Return ONLY valid JSON. No markdown, no preamble, no trailing text.

The JSON schema you MUST follow exactly:

{
“overall_score”: <integer 0-100>,
“grade”: <“A”|“B”|“C”|“D”|“F”>,
“executive_summary”: “<2-3 sentence honest summary of the site’s digital health>”,
“estimated_monthly_revenue_lost”: “<WILL BE OVERRIDDEN — just put null here>”,
“categories”: [
{
“name”: “<category name>”,
“score”: <integer 0-100>,
“icon”: “<single emoji>”,
“status”: <“critical”|“warning”|“good”>,
“summary”: “<1 sentence>”,
“issues”: [
{
“severity”: <“critical”|“warning”|“pass”>,
“title”: “<short title>”,
“detail”: “<specific finding with actual data from the scan>”,
“fix”: “<concrete actionable fix, 1-2 sentences>”,
“impact”: <“high”|“medium”|“low”>,
“effort”: <“easy”|“medium”|“hard”>
}
]
}
],
“quick_wins”: [
{
“title”: “<action title>”,
“detail”: “<what to do specifically>”,
“time_to_fix”: “<e.g. 15 minutes>”,
“expected_impact”: “<expected outcome>”
}
],
“competitive_risks”: “<paragraph about what competitors who fix these issues will have over this site>”,
“priority_roadmap”: [
{ “week”: 1, “focus”: “<what to fix in week 1>”, “items”: [”<item>”, “<item>”] },
{ “week”: 2, “focus”: “<what to fix in week 2>”, “items”: [”<item>”, “<item>”] },
{ “week”: 4, “focus”: “<what to fix in month 1>”, “items”: [”<item>”, “<item>”] }
]
}

Categories MUST include all of these in this order:

1. SEO & Discoverability
1. Page Speed & Performance
1. Mobile Experience
1. Conversion Optimization
1. Trust & Credibility
1. Content Quality
1. Technical Health
1. Social & Sharing

Use the ACTUAL scraped data below. Reference real numbers. Be specific.
If a number is bad (e.g. load_time_ms > 3000), call it out forcefully.
If something is missing (meta_description is null), call it out as a real problem.

SCRAPED DATA:
“””

def analyze_with_claude(scraped_data: dict) -> dict:
“”“Send scraped data to Claude, get structured JSON analysis back.”””
data_str = json.dumps(scraped_data, indent=2, default=str)

```
message = claude.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4000,
    messages=[
        {
            "role": "user",
            "content": ANALYSIS_PROMPT + data_str
        }
    ]
)

raw = message.content[0].text.strip()
# Strip accidental markdown fences
raw = re.sub(r"^```json\s*", "", raw)
raw = re.sub(r"```$", "", raw.strip())

return json.loads(raw)
```

# ── API Routes ─────────────────────────────────────────────────────────────────

@app.get(”/”)
def root():
return {“status”: “SnapshotAI running”, “version”: “1.0.0”}

@app.get(”/health”)
def health():
return {“ok”: True}

@app.post(”/scan/preview”)
def scan_preview(req: ScanRequest):
“””
Free endpoint — scrape + Claude analysis, return preview (5 issues).
Called before payment.
“””
url = req.url.strip()
if not url:
raise HTTPException(400, “URL is required”)

```
try:
    scraped = scrape_website(url)
except Exception as e:
    raise HTTPException(422, f"Could not fetch website: {str(e)}")

try:
    analysis = analyze_with_claude(scraped)
except Exception as e:
    raise HTTPException(500, f"Analysis failed: {str(e)}")

# Build report ID (deterministic for same URL)
# Override Claude's revenue estimate with deterministic calculation
# Same URL = same number every time, no AI randomness
analysis["estimated_monthly_revenue_lost"] = calculate_revenue_lost(scraped, analysis["overall_score"])

report_id = hashlib.md5(url.encode()).hexdigest()[:12]

# Store full analysis for later PDF generation
cache_path = f"{REPORTS_DIR}/{report_id}.json"
with open(cache_path, "w") as f:
    json.dump({"scraped": scraped, "analysis": analysis}, f)

# Flatten all issues across categories for preview
all_issues = []
for cat in analysis.get("categories", []):
    for issue in cat.get("issues", []):
        issue["category"] = cat["name"]
        all_issues.append(issue)

# Sort: critical first, then warning
severity_order = {"critical": 0, "warning": 1, "pass": 2}
all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "pass"), 2))

return {
    "report_id": report_id,
    "domain": scraped["domain"],
    "score": analysis["overall_score"],
    "grade": analysis["grade"],
    "executive_summary": analysis["executive_summary"],
    "estimated_revenue_lost": analysis.get("estimated_monthly_revenue_lost", "Unknown"),
    "preview_issues": all_issues[:5],   # only first 5 free
    "total_issues_found": len(all_issues),
    "categories_summary": [
        {
            "name": c["name"],
            "score": c["score"],
            "icon": c["icon"],
            "status": c["status"]
        }
        for c in analysis.get("categories", [])
    ]
}
```

@app.post(”/report/generate”)
def generate_report(report_id: str, email: Optional[str] = None):
“””
Called after successful Stripe payment.
Reads cached analysis and generates full PDF.
“””
cache_path = f”{REPORTS_DIR}/{report_id}.json”
if not os.path.exists(cache_path):
raise HTTPException(404, “Report not found. Please run a new scan.”)

```
with open(cache_path) as f:
    data = json.load(f)

scraped  = data["scraped"]
analysis = data["analysis"]

pdf_path = f"{REPORTS_DIR}/{report_id}.pdf"

try:
    generate_pdf_report(scraped, analysis, pdf_path)
except Exception as e:
    raise HTTPException(500, f"PDF generation failed: {str(e)}")

return FileResponse(
    pdf_path,
    media_type="application/pdf",
    filename=f"SnapshotAI-Report-{scraped['domain']}.pdf"
)
```

@app.get(”/report/download/{report_id}”)
def download_report(report_id: str):
“”“Direct download link (sent via email after payment).”””
pdf_path = f”{REPORTS_DIR}/{report_id}.pdf”
if not os.path.exists(pdf_path):
raise HTTPException(404, “Report PDF not found”)
return FileResponse(
pdf_path,
media_type=“application/pdf”,
filename=f”SnapshotAI-Report-{report_id}.pdf”
)