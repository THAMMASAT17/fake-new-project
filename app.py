from flask import Flask, render_template, request, jsonify, make_response
import json
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from groq import Groq
from dotenv import load_dotenv
from ddgs import DDGS
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)

# ======================
# AI
# ======================

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 🟢 เชื่อมต่อ Supabase
SUPABASE_URL = "https://jeggrrvcjhcxevzfltok.supabase.co"
SUPABASE_KEY = "sb_publishable_BQaWPVvo7XPPx6hzZ6QVYg_67qKGY-l"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# TRUSTED NEWS SOURCES
# ======================

TRUSTED_DOMAINS = [

"thairath.co.th",
"khaosod.co.th",
"matichon.co.th",
"thaipbs.or.th",
"dailynews.co.th",
"sanook.com",
"kapook.com",
"daradaily.com",

"bbc.com",
"reuters.com",
"cnn.com",
"apnews.com",
"theguardian.com",

"soompi.com",
"allkpop.com",
"koreaboo.com"
]

# ======================
# CLICKBAIT WORDS
# ======================

CLICKBAIT = [
"ด่วน",
"ช็อก",
"อึ้ง",
"แชร์ด่วน",
"ก่อนโดนลบ",
"ห้ามพลาด"
]

# ======================
# SCAM WORDS
# ======================

SCAM = [
"แจกเงินฟรี",
"แชร์โพสต์นี้",
"รับเงินฟรี",
"โอนเงินฟรี",
"รับเงินทันที"
]

# ======================
# SCRAPE NEWS
# ======================

def scrape_news(url, snippet):

    try:

        headers = {'User-Agent': 'Mozilla/5.0'}

        r = requests.get(url, headers=headers, timeout=5)

        soup = BeautifulSoup(r.content, 'html.parser')

        p = soup.find_all("p")

        text = " ".join([x.get_text(strip=True) for x in p])

        if text:
            return text[:2000]

        return snippet

    except:
        return snippet

# ======================
# SEARCH NEWS
# ======================

def search_news(query):

    results = []
    seen = set()

    with DDGS() as ddgs:

        search = ddgs.text(query, region="th-th", max_results=20)

        for r in search:

            link = r.get("href", "")

            if not link or link in seen:
                continue

            clean = link.replace("https://", "").replace("http://", "")

            if any(domain in clean for domain in TRUSTED_DOMAINS):

                seen.add(link)

                snippet = r.get("body", "")

                body = scrape_news(link, snippet)

                results.append({

                    "title": r.get("title", ""),
                    "body": body,
                    "link": link,
                    "domain": urlparse(link).netloc

                })

            if len(results) >= 3:
                break

    return results

# ======================
# CLICKBAIT DETECTION
# ======================

def detect_clickbait(text):

    for w in CLICKBAIT:
        if w in text:
            return True

    return False

# ======================
# SCAM DETECTION
# ======================

def detect_scam(text):

    for w in SCAM:
        if w in text:
            return True

    return False

# ======================
# FACT CHECK
# ======================

def fact_check(text, web_data):

    if not web_data:
        return "⚠ Fake", "ไม่พบข่าวจากแหล่งข่าวที่เชื่อถือได้", 20

    match_score = 0

    for news in web_data:
        if any(word in news["body"] for word in text.split()):
            match_score += 1

    if match_score == 0:
        return "⚠ Fake", "ไม่พบเนื้อหาข่าวที่ตรงกับข้อความ", 25

    confidence = min(60 + match_score*10, 90)

    return "✔ Real", "พบข่าวที่มีเนื้อหาตรงกับข้อความ", confidence

# ======================
# ROUTE
# ======================

@app.route("/", methods=["GET", "POST"])
def index():

    context = {}

    try:

        history = supabase.table("search_history")\
        .select("id,user_query")\
        .order("created_at", desc=True)\
        .limit(5)\
        .execute()

        context["histories"] = history.data

    except:
        context["histories"] = []

    if request.method == "POST":

        news = request.form["news"].strip()

        start = time.time()

        web_data = search_news(news)

        result, reason, confidence = fact_check(news, web_data)

        process_time = round(time.time() - start, 2)

        try:

            supabase.table("search_history").insert({

                "user_query": news,
                "ai_result": result,
                "ai_reason": reason,
                "confidence": confidence,
                "sources": web_data

            }).execute()

        except:
            pass

        context.update({

            "result": result,
            "reason": reason,
            "confidence": confidence,
            "references": web_data,
            "news": news,
            "process_time": process_time,

            "signals": ["Trusted News Sources", "AI Fact Check"],
            "keywords": news.split(" ")[:5]

        })

    response = make_response(render_template("index.html", **context))

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

# ======================

@app.route("/feedback", methods=["POST"])
def feedback():

    data = request.json

    record_id = data.get("id")

    status = data.get("status")

    try:

        supabase.table("search_history")\
        .update({"user_feedback": status})\
        .eq("id", record_id)\
        .execute()

        return jsonify({"success": True})

    except:

        return jsonify({"success": False})

# ======================

if __name__ == "__main__":

    app.run(debug=True)