from flask import Flask, render_template, request, jsonify, make_response
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
from ddgs import DDGS
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)

# 🟢 เชื่อมต่อ Supabase
SUPABASE_URL = "https://jeggrrvcjhcxevzfltok.supabase.co"
SUPABASE_KEY = "sb_publishable_BQaWPVvo7XPPx6hzZ6QVYg_67qKGY-l"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================================
# TRUSTED NEWS DOMAINS
# ================================

TRUSTED_DOMAINS = [

"thairath.co.th",
"khaosod.co.th",
"matichon.co.th",
"thaipbs.or.th",
"dailynews.co.th",
"sanook.com",
"kapook.com",

"bbc.com",
"cnn.com",
"reuters.com",
"apnews.com",
"theguardian.com",

"soompi.com",
"allkpop.com"

]

# ================================
# CLICKBAIT WORDS
# ================================

CLICKBAIT = [

"ด่วน",
"ช็อก",
"อึ้ง",
"แชร์ด่วน",
"ก่อนโดนลบ",
"ห้ามพลาด",
"คุณจะไม่เชื่อ"
]

# ================================
# SCAM WORDS
# ================================

SCAM = [

"แจกเงินฟรี",
"แชร์โพสต์นี้",
"รับเงินฟรี",
"รับเงินทันที",
"โอนเงินให้",
"กดลิงก์รับเงิน"
]

# ================================
# SCRAPE NEWS
# ================================

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

# ================================
# SEARCH NEWS
# ================================

def search_news(query):

    results = []
    seen = set()

    try:

        with DDGS() as ddgs:

            search = ddgs.text(query, region="th-th", max_results=20)

            for r in search:

                link = r.get("href","")

                if not link or link in seen:
                    continue

                clean = link.replace("https://","").replace("http://","")

                if any(domain in clean for domain in TRUSTED_DOMAINS):

                    seen.add(link)

                    snippet = r.get("body","")

                    body = scrape_news(link, snippet)

                    results.append({

                        "title": r.get("title",""),
                        "body": body,
                        "link": link,
                        "domain": urlparse(link).netloc

                    })

                if len(results) >= 3:
                    break

    except Exception as e:

        print("Search error:", e)

    return results

# ================================
# CLICKBAIT DETECT
# ================================

def detect_clickbait(text):

    for w in CLICKBAIT:
        if w in text:
            return True

    return False

# ================================
# SCAM DETECT
# ================================

def detect_scam(text):

    for w in SCAM:
        if w in text:
            return True

    return False

# ================================
# FACT CHECK LOGIC
# ================================

def fact_check(text, web_data):

    # scam

    if detect_scam(text):
        return "Fake","ข้อความเข้าข่ายหลอกลวง",10

    # clickbait

    if detect_clickbait(text):
        return "Fake","ข้อความมีลักษณะ clickbait",20

    # ไม่มีข่าวเลย

    if not web_data:
        return "Fake","ไม่พบข่าวจากแหล่งข่าวที่เชื่อถือได้",25

    # มีข่าวหลายแหล่ง

    if len(web_data) >= 2:

        confidence = min(70 + len(web_data)*5, 90)

        return "Real","พบข่าวจากหลายแหล่งข่าวที่เชื่อถือได้",confidence

    # มีแหล่งเดียว

    return "Real","พบข่าวจากแหล่งข่าวที่เชื่อถือได้",65

# ================================
# MAIN ROUTE
# ================================

@app.route("/", methods=["GET","POST"])
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

        # =====================
        # CACHE CHECK
        # =====================

        cached = supabase.table("search_history")\
        .select("*")\
        .eq("user_query", news)\
        .limit(1)\
        .execute()

        if cached.data:

            c = cached.data[0]

            context.update({

                "result": c["ai_result"],
                "reason": c["ai_reason"],
                "confidence": c["confidence"],
                "references": c["sources"],
                "news": news,
                "process_time": 0.1,
                "signals": ["Cache Result"],
                "keywords": news.split(" ")[:5]

            })

            return render_template("index.html", **context)

        # =====================
        # SEARCH NEWS
        # =====================

        web_data = search_news(news)

        result, reason, confidence = fact_check(news, web_data)

        process_time = round(time.time() - start,2)

        try:

            supabase.table("search_history").insert({

                "user_query": news,
                "ai_result": result,
                "ai_reason": reason,
                "confidence": confidence,
                "sources": web_data

            }).execute()

        except Exception as e:

            print("DB error:", e)

        context.update({

            "result": result,
            "reason": reason,
            "confidence": confidence,
            "references": web_data,
            "news": news,
            "process_time": process_time,
            "signals": ["Trusted Sources","AI Fact Check"],
            "keywords": news.split(" ")[:5]

        })

    response = make_response(render_template("index.html", **context))

    response.headers["Cache-Control"] = "no-cache"

    return response

# ================================
# FEEDBACK
# ================================

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

# ================================

if __name__ == "__main__":

    app.run(debug=True)