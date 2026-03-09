from flask import Flask, render_template, request, jsonify
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
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 🟢 เชื่อมต่อ Supabase
SUPABASE_URL = "https://jeggrrvcjhcxevzfltok.supabase.co"
SUPABASE_KEY = "sb_publishable_BQaWPVvo7XPPx6hzZ6QVYg_67qKGY-l"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🟢 TRUSTED_DOMAINS: รวมสำนักข่าวไทย, ต่างประเทศ และเพจ Social Media ทางการ
TRUSTED_DOMAINS = {
    "Health": [
        "rama.mahidol.ac.th", "fda.moph.go.th", "sure.tna.mcot.net", "pobpad.com", "chula.ac.th", 
        "thairath.co.th", "thaipbs.or.th", "who.int", "wikipedia.org",
        "cdc.gov", "nih.gov", "mayoclinic.org", "clevelandclinic.org", "thelancet.com", "nejm.org", "hopkinsmedicine.org",
        "facebook.com/thairath", "facebook.com/thaipbs", "x.com/Thairath_News", "twitter.com/Thairath_News"
    ],
    "Economy": [
        "bot.or.th", "set.or.th", "prachachat.net", "thansettakij.com", "bangkokbiznews.com", 
        "kaohoon.com", "bloomberg.com", "reuters.com", "wikipedia.org",
        "ft.com", "wsj.com", "cnbc.com", "forbes.com", "economist.com", "worldbank.org", "imf.org",
        "facebook.com/prachachat", "facebook.com/bangkokbiznews", "x.com/prachachat"
    ],
    "Accident_Crime": [
        "thairath.co.th", "khaosod.co.th", "dailynews.co.th", "matichon.co.th", "thaipbs.or.th", 
        "bbc.com", "cnn.com", "wikipedia.org",
        "apnews.com", "nytimes.com", "washingtonpost.com", "theguardian.com", "aljazeera.com",
        "facebook.com/thairath", "facebook.com/KhaosodOnline", "facebook.com/MatichonOnline", "x.com/KhaosodOnline"
    ],
    "Entertainment": [
        "thairath.co.th", "daradaily.com", "nineentertain.mcot.net", "sanook.com", 
        "soompi.com", "allkpop.com", "wikipedia.org",
        "variety.com", "hollywoodreporter.com", "deadline.com", "billboard.com", "ew.com", "rollingstone.com",
        "facebook.com/nineentertain", "facebook.com/daradaily", "x.com/nineentertain"
    ],
    "General": [
        "thairath.co.th", "khaosod.co.th", "matichon.co.th", "thaipbs.or.th", "dailynews.co.th", 
        "bbc.com", "reuters.com", "wikipedia.org",
        "apnews.com", "npr.org", "aljazeera.com", "theguardian.com", "time.com", "nbcnews.com",
        "facebook.com/thairath", "facebook.com/KhaosodOnline", "facebook.com/MatichonOnline", "x.com/KhaosodOnline", "twitter.com/KhaosodOnline"
    ]
}

def classify_and_route(text):
    # ปรับ Prompt เป็นภาษาไทย เพื่อบังคับให้ AI คิดและสกัดคำค้นหาเป็นภาษาไทย 100%
    prompt = f"""
    วิเคราะห์ข้อความต่อไปนี้ที่ผู้ใช้ต้องการตรวจสอบข้อเท็จจริง: "{text}"

    งานที่ 1: สกัดข้อกล่าวอ้างหลัก (Exact Claim) ระบุให้ชัดเจนว่า ใคร ทำอะไร ที่ไหน เมื่อไหร่ เขียนสรุปข้อกล่าวอ้างเป็น "ภาษาไทย" แบบตรงไปตรงมา ห้ามใช้คำที่แสดงความไม่แน่ใจ (เช่น น่าจะ, อาจจะ)
    งานที่ 2: จัดหมวดหมู่ (Category) ให้อยู่ในหมวดใดหมวดหนึ่งต่อไปนี้เท่านั้น: "Health", "Economy", "Entertainment", "Accident_Crime", หรือ "General"
    งานที่ 3: สร้างคำค้นหา (Search Queries) เป็น "ภาษาไทย" 2 ประโยคที่ปรับแต่งมาอย่างดีสำหรับ Search Engine
    - Query 1: ใช้คำนามเฉพาะภาษาไทย ชื่อเต็ม องค์กร และคำที่ระบุบริบทชัดเจน หากมีชื่อต่างชาติให้ทับศัพท์หรือแปลเป็นไทยให้ถูกต้อง หลีกเลี่ยงคำกว้างๆ
    - Query 2: คำค้นหาภาษาไทยทางเลือกที่เน้นเหตุการณ์หรือบริบทโดยรวม เพื่อใช้ยืนยันข้อกล่าวอ้าง

    ตอบกลับเป็น JSON ตามโครงสร้างนี้เท่านั้น:
    {{
        "exact_claim": "สรุปข้อกล่าวอ้างสั้นๆ กระชับ เป็นข้อเท็จจริง (ภาษาไทย)",
        "category": "...", 
        "queries": ["คำค้นหาภาษาไทยที่เจาะจง 1", "คำค้นหาภาษาไทยทางเลือก 2"]
    }}
    """
    try:
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a precise search query optimizer. Output ONLY JSON."}, {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            temperature=0.1
        )
        data = json.loads(res.choices[0].message.content)
        return (
            data.get("category", "General"), 
            data.get("queries", [text[:30]]), 
            data.get("exact_claim", "ไม่สามารถวิเคราะห์บริบทได้")
        )
    except:
        return "General", [text[:30]], "ระบบเกิดข้อผิดพลาดในการดึงข้อมูล"

def scrape_full_news(url, ddg_snippet=""):
    # 🟢 บายพาสการใช้ BeautifulSoup หากเป็นลิงก์ Social Media เพื่อป้องกันการโดนบล็อก
    if any(sm in url.lower() for sm in ["facebook.com", "twitter.com", "x.com"]):
        return f"ข้อมูลสรุปจากผลการค้นหา (โซเชียลมีเดีย): {ddg_snippet}"

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = " ".join([p.get_text(strip=True) for p in paragraphs])
        return full_text[:2000] if full_text else f"ดึงเนื้อหาเต็มไม่ได้ อ้างอิงจากสรุป: {ddg_snippet}"
    except Exception:
        return f"เว็บไซต์ขัดข้อง อ้างอิงจากสรุป: {ddg_snippet}"

def search_strict_thai_news(category, queries):
    results = []
    seen_links = set()
    allowed_domains = TRUSTED_DOMAINS.get(category, TRUSTED_DOMAINS["General"])
    
    try:
        with DDGS() as ddgs:
            for search_q in queries:
                if len(results) >= 3: 
                    break 
                
                print(f"🔍 Searching for: {search_q}")
                search_results = ddgs.text(search_q, region='th-th', safesearch='off', max_results=20)
                
                if search_results:
                    for r in search_results:
                        link = r.get('href', '')
                        if not link or link in seen_links: continue
                        
                        # 🟢 ลบโปรโตคอลออกเพื่อให้เช็กชื่อโดเมนและพาร์ทของเพจโซเชียลได้ (เช่น facebook.com/thairath)
                        clean_url = link.replace("https://", "").replace("http://", "").replace("www.", "")
                        
                        if any(trusted.lower() in clean_url.lower() for trusted in allowed_domains):
                            seen_links.add(link)
                            
                            # 🟢 ดึง snippet จาก DuckDuckGo มาใช้งานเป็นตัวสำรองสำหรับ Social Media
                            ddg_snippet = r.get('body', '')
                            full_content = scrape_full_news(link, ddg_snippet)
                            
                            results.append({
                                "title": r.get('title', ''),
                                "body": full_content,
                                "link": link,
                                "domain": urlparse(link).netloc.replace("www.", "")
                            })
                        if len(results) >= 3: break
                time.sleep(1) 
    except Exception as e:
        print(f"❌ Search Error: {e}")
    return results

def analyze_logic_by_category(text, exact_claim, category, web_data, queries):
    if not web_data:
        web_context = "🛑 ไม่พบข้อมูลอ้างอิง"
    else:
        web_context = ""
        for i, d in enumerate(web_data):
            web_context += f"อ้างอิง {i+1} [{d['domain']}]: {d['title']}\nเนื้อหา: {d['body']}\n\n"

    prompt = f"""
    ผู้ใช้ต้องการตรวจสอบข้อความ: "{text}"
    ข้อกล่าวอ้างหลัก (วิเคราะห์โดย AI): "{exact_claim}"
    
    ข้อมูลจากสื่อที่เชื่อถือได้ที่ค้นพบ:
    {web_context}

    คำสั่งในการตรวจสอบ (ทำตามลำดับอย่างเคร่งครัด):
    1. **เช็คความเกี่ยวข้องก่อน:** ตรวจสอบว่า "ข้อมูลจากสื่อ" กล่าวถึงบุคคล หรือ เรื่องราวเดียวกับ "ข้อความของผู้ใช้" หรือไม่? 
    2. ถ้าข้อมูลจากสื่อ **ไม่เกี่ยวข้องเลย** (เช่น ผู้ใช้ถามเรื่องหนึ่ง แต่สื่อรายงานอีกเรื่องหนึ่ง) ให้ตอบ result เป็น '❓ Insufficient Data' และ reason ให้อธิบายว่า "แหล่งอ้างอิงที่สืบค้นได้ ไม่ตรงกับเรื่องราวที่ต้องการตรวจสอบ" (ห้ามตอบ Fake News เด็ดขาดถ้าคนละเรื่องกัน)
    3. ถ้าข้อมูลจากสื่อ **ตรงประเด็น** และเนื้อหาชี้ว่าสิ่งที่ผู้ใช้ถามเป็น **เท็จ** ให้ตอบ '⚠ Fake News Risk'
    4. ถ้าข้อมูลจากสื่อ **ตรงประเด็น** และเนื้อหาชี้ว่าสิ่งที่ผู้ใช้ถามเป็น **ความจริง** ให้ตอบ '✔ Likely Real'
    5. ถ้าข้อมูลก้ำกึ่ง ให้ตอบ '⚠ Possibly Misleading'

    Output ONLY JSON in this structure:
    {{
        "result": "'✔ Likely Real', '⚠ Fake News Risk', '⚠ Possibly Misleading', or '❓ Insufficient Data'",
        "reason": "สรุปข้อมูลที่พบ หรือแจ้งว่าข้อมูลที่หามาได้ไม่ตรงกับเรื่องที่ถาม (เป็นภาษาไทย)",
        "confidence": <integer 0-100>
    }}
    """
    try:
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a strict, logical fact-checker. Output ONLY JSON."}, {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            temperature=0.0
        )
        data = json.loads(res.choices[0].message.content)
        return data.get("result"), data.get("reason"), data.get("confidence", 50), queries, category
    except Exception as e:
        return "⚠ Error", f"ระบบ AI ขัดข้อง: {str(e)}", 0, [], "Unknown"

@app.route("/", methods=["GET","POST"])
def index():
    context = {}
    
    try:
        history_response = supabase.table("search_history").select("id, user_query").order("created_at", desc=True).limit(5).execute()
        context['histories'] = history_response.data
    except:
        context['histories'] = []

    if request.method == "POST":
        news = request.form["news"].strip()
        start_time = time.time()
        
        try:
            cached_res = supabase.table("search_history").select("*").eq("user_query", news).eq("user_feedback", "accurate").limit(1).execute()
            if cached_res.data:
                print("⚡ ดึงข้อมูลจาก Cache ที่น่าเชื่อถือ!")
                c_data = cached_res.data[0]
                process_time = round(time.time() - start_time, 2)
                context.update({
                    'result': c_data['ai_result'],
                    'reason': c_data['ai_reason'],
                    'confidence': c_data['confidence'],
                    'keywords': [news[:15]+"..."], 
                    'signals': ["Verified Cache"],
                    'category': c_data.get('category', 'General'),
                    'references': c_data.get('sources', []),
                    'news': news,
                    'record_id': c_data['id'],
                    'process_time': process_time,
                    'is_cached': True,
                    'exact_claim': c_data.get('user_query', news)
                })
                return render_template("index.html", **context)
        except Exception as e:
            print("Cache check error:", e)

        category, queries, exact_claim = classify_and_route(news)
        print(f"🧠 AI Exact Claim: {exact_claim}")
        
        web_data = search_strict_thai_news(category, queries)
        
        result, reason, confidence, keywords, category = analyze_logic_by_category(news, exact_claim, category, web_data, queries)
        references = web_data[:4] 

        process_time = round(time.time() - start_time, 2)

        try:
            db_insert = supabase.table("search_history").insert({
                "user_query": news,
                "category": category,
                "ai_result": result,
                "ai_reason": reason,
                "confidence": confidence,
                "sources": references
            }).execute()
            context['record_id'] = db_insert.data[0]['id']
        except Exception as e:
            print(f"Db Insert Error: {e}")

        context.update({
            'result': result, 
            'reason': reason, 
            'confidence': confidence,
            'keywords': keywords, 
            'signals': [category, "Fact-Checked"], 
            'category': category, 
            'references': references, 
            'news': news, 
            'process_time': process_time, 
            'is_cached': False,
            'exact_claim': exact_claim 
        })

    return render_template("index.html", **context)

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    record_id = data.get("id")
    status = data.get("status") 
    
    try:
        supabase.table("search_history").update({"user_feedback": status}).eq("id", record_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(debug=True)