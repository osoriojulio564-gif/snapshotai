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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic

from report_generator import generate_pdf_report

app = FastAPI(title="SnapshotAI Report Generator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REPORTS_DIR = "/tmp/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

class ScanRequest(BaseModel):
    url: str
    email: Optional[str] = None

@app.get("/")
def root():
    return {"status": "SnapshotAI running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"ok": True}

def scrape_website(url: str) -> dict:
    if not url.startswith("http"):
        url = "https://" + url
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    start = time.time()
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    except requests.exceptions.SSLError:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True, verify=False)
    load_time_ms = int((time.time() - start) * 1000)
    soup = BeautifulSoup(resp.text, "html.parser")
    final_url = resp.url
    parsed = urllib.parse.urlparse(final_url)
    domain = parsed.netloc
    title_tag = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_robots = soup.find("meta", attrs={"name": "robots"})
    canonical = soup.find("link", rel="canonical")
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    viewport = soup.find("meta", attrs={"name": "viewport"})
    charset = soup.find("meta", attrs={"charset": True})
    lang_attr = soup.find("html").get("lang", "") if soup.find("html") else ""
    structured_data = soup.find_all("script", type="application/ld+json")
    h1s = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
    h3s = [h.get_text(strip=True) for h in soup.find_all("h3")]
    body_text = soup.get_text(separator=" ", strip=True)
    word_count = len(body_text.split())
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
    images = soup.find_all("img")
    images_without_alt = [img.get("src", "")[:80] for img in images if not img.get("alt")]
    all_links = soup.find_all("a", href=True)
    internal_links = [a["href"] for a in all_links if domain in a["href"] or a["href"].startswith("/")]
    external_links = [a["href"] for a in all_links if a["href"].startswith("http") and domain not in a["href"]]
    buttons = soup.find_all("button")
    cta_texts = [b.get_text(strip=True) for b in buttons if b.get_text(strip=True)]
    forms = soup.find_all("form")
    https_active = final_url.startswith("https://")
    has_phone = bool(re.search(r'\+?[\d\s\-\(\)]{7,}', body_text))
    privacy_link = any("privacy" in a.get("href", "").lower() for a in all_links)
    terms_link = any("terms" in a.get("href", "").lower() for a in all_links)
    social_links = [a["href"] for a in all_links if any(s in a["href"] for s in ["facebook.com","twitter.com","instagram.com","linkedin.com","tiktok.com","youtube.com"])]
    review_keywords = bool(re.search(r'review|testimonial|stars|rated|trustpilot', body_text, re.I))
    scripts = soup.find_all("script", src=True)
    stylesheets = soup.find_all("link", rel="stylesheet")
    lazy_images = [img for img in images if img.get("loading") == "lazy"]
    html_size_kb = round(len(resp.text) / 1024, 1)
    favicon = soup.find("link", rel=lambda r: r and "icon" in r)
    responsive_css = "media" in resp.text.lower()

    return {
        "url": final_url, "domain": domain, "status_code": resp.status_code,
        "load_time_ms": load_time_ms, "html_size_kb": html_size_kb, "https": https_active,
        "title": title_tag.get_text(strip=True) if title_tag else None,
        "title_length": len(title_tag.get_text(strip=True)) if title_tag else 0,
        "meta_description": meta_desc.get("content", "").strip() if meta_desc else None,
        "meta_desc_length": len(meta_desc.get("content", "")) if meta_desc else 0,
        "canonical_url": canonical.get("href") if canonical else None,
        "lang": lang_attr, "charset_declared": charset is not None,
        "robots_meta": meta_robots.get("content", "") if meta_robots else None,
        "structured_data_count": len(structured_data),
        "og_title": og_title.get("content") if og_title else None,
        "og_description": og_desc.get("content") if og_desc else None,
        "og_image": og_image.get("content") if og_image else None,
        "twitter_card": twitter_card.get("content") if twitter_card else None,
        "h1_count": len(h1s), "h1_texts": h1s[:5],
        "h2_count": len(h2s), "h2_texts": h2s[:10], "h3_count": len(h3s),
        "word_count": word_count, "paragraph_count": len(paragraphs),
        "first_paragraphs": paragraphs[:4],
        "image_count": len(images), "images_without_alt": len(images_without_alt),
        "lazy_images": len(lazy_images),
        "internal_link_count": len(internal_links), "external_link_count": len(external_links),
        "button_count": len(buttons), "cta_texts": cta_texts[:10], "form_count": len(forms),
        "has_phone": has_phone, "has_privacy_link": privacy_link, "has_terms_link": terms_link,
        "social_links": social_links[:8], "has_reviews_testimonials": review_keywords,
        "has_favicon": favicon is not None,
        "external_scripts_count": len(scripts), "stylesheets_count": len(stylesheets),
        "has_viewport_meta": viewport is not None,
        "viewport_content": viewport.get("content", "") if viewport else "",
        "responsive_css_detected": responsive_css,
    }

ANALYSIS_PROMPT = """
You are a senior digital marketing consultant and technical SEO expert.
You have just received raw scraped data from a website audit tool.
Return ONLY valid JSON. No markdown, no preamble, no trailing text.

{
  "overall_score": <integer 0-100>,
  "grade": <"A"|"B"|"C"|"D"|"F">,
  "executive_summary": "<2-3 sentence honest summary>",
  "estimated_monthly_revenue_lost": "<dollar range e.g. '$1,200-$3,400/mo'>",
  "categories": [
    {
      "name": "<category name>",
      "score": <integer 0-100>,
      "icon": "<single emoji>",
      "status": <"critical"|"warning"|"good">,
      "summary": "<1 sentence>",
      "issues": [
        {
          "severity": <"critical"|"warning"|"pass">,
          "title": "<short title>",
          "detail": "<specific finding with actual data>",
          "fix": "<concrete actionable fix>",
          "impact": <"high"|"medium"|"low">,
          "effort": <"easy"|"medium"|"hard">
        }
      ]
    }
  ],
  "quick_wins": [
    {
      "title": "<action title>",
      "detail": "<what to do specifically>",
      "time_to_fix": "<e.g. 15 minutes>",
      "expected_impact": "<expected outcome>"
    }
  ],
  "competitive_risks": "<paragraph about competitive risks>",
  "priority_roadmap": [
    { "week": 1, "focus": "<focus>", "items": ["<item>", "<item>"] },
    { "week": 2, "focus": "<focus>", "items": ["<item>", "<item>"] },
    { "week": 4, "focus": "<focus>", "items": ["<item>", "<item>"] }
  ]
}

Categories MUST include: SEO & Discoverability, Page Speed & Performance, Mobile Experience, Conversion Optimization, Trust & Credibility, Content Quality, Technical Health, Social & Sharing.
Use the ACTUAL scraped data. Reference real numbers. Be specific and ruthlessly honest.

SCRAPED DATA:
"""

def analyze_with_claude(scraped_data: dict) -> dict:
    data_str = json.dumps(scraped_data, indent=2, default=str)
    message = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": ANALYSIS_PROMPT + data_str}]
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```$", "", raw.strip())
    return json.loads(raw)

@app.post("/scan/preview")
def scan_preview(req: ScanRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(400, "URL is required")
    try:
        scraped = scrape_website(url)
    except Exception as e:
        raise HTTPException(422, f"Could not fetch website: {str(e)}")
    try:
        analysis = analyze_with_claude(scraped)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")
    report_id = hashlib.md5(url.encode()).hexdigest()[:12]
    cache_path = f"{REPORTS_DIR}/{report_id}.json"
    with open(cache_path, "w") as f:
        json.dump({"scraped": scraped, "analysis": analysis}, f)
    all_issues = []
    for cat in analysis.get("categories", []):
        for issue in cat.get("issues", []):
            issue["category"] = cat["name"]
            all_issues.append(issue)
    severity_order = {"critical": 0, "warning": 1, "pass": 2}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "pass"), 2))
    return {
        "report_id": report_id,
        "domain": scraped["domain"],
        "score": analysis["overall_score"],
        "grade": analysis["grade"],
        "executive_summary": analysis["executive_summary"],
        "estimated_revenue_lost": analysis.get("estimated_monthly_revenue_lost", "Unknown"),
        "preview_issues": all_issues[:5],
        "total_issues_found": len(all_issues),
        "categories_summary": [
            {"name": c["name"], "score": c["score"], "icon": c["icon"], "status": c["status"]}
            for c in analysis.get("categories", [])
        ]
    }

@app.post("/report/generate")
def generate_report(report_id: str, email: Optional[str] = None):
    cache_path = f"{REPORTS_DIR}/{report_id}.json"
    if not os.path.exists(cache_path):
        raise HTTPException(404, "Report not found. Please run a new scan.")
    with open(cache_path) as f:
        data = json.load(f)
    scraped = data["scraped"]
    analysis = data["analysis"]
    pdf_path = f"{REPORTS_DIR}/{report_id}.pdf"
    try:
        generate_pdf_report(scraped, analysis, pdf_path)
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {str(e)}")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"SnapshotAI-Report-{scraped['domain']}.pdf")

@app.get("/report/download/{report_id}")
def download_report(report_id: str):
    pdf_path = f"{REPORTS_DIR}/{report_id}.pdf"
    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Report PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"SnapshotAI-Report-{report_id}.pdf")
