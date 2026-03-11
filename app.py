from flask import Flask, render_template, request, jsonify
import json
import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from groq import Groq
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
# 🟢 ดึง API Key ของ Groq จาก .env
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 🟢 เชื่อมต่อ Supabase โดยดึงค่าจาก .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# (Optional) เช็กเพื่อป้องกันความผิดพลาดกรณีหาตัวแปรไม่เจอ
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("ไม่พบค่า SUPABASE_URL หรือ SUPABASE_KEY ในไฟล์ .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🟢 TRUSTED_DOMAINS: ยุบรวมทุกลิงก์ที่น่าเชื่อถือ ไม่แยกหมวดหมู่แล้ว
TRUSTED_DOMAINS = [
    "rama.mahidol.ac.th", "fda.moph.go.th", "sure.tna.mcot.net", "pobpad.com", "chula.ac.th", 
    "thairath.co.th", "thaipbs.or.th", "who.int", "wikipedia.org",
    "cdc.gov", "nih.gov", "mayoclinic.org", "clevelandclinic.org", "thelancet.com", "nejm.org", "hopkinsmedicine.org",
    "bot.or.th", "set.or.th", "prachachat.net", "thansettakij.com", "bangkokbiznews.com", 
    "kaohoon.com", "bloomberg.com", "reuters.com", "ft.com", "wsj.com", "cnbc.com", "forbes.com", "economist.com", 
    "worldbank.org", "imf.org", "khaosod.co.th", "dailynews.co.th", "matichon.co.th", 
    "bbc.com", "cnn.com", "apnews.com", "nytimes.com", "washingtonpost.com", "theguardian.com", "aljazeera.com",
    "daradaily.com", "nineentertain.mcot.net", "sanook.com", "soompi.com", "allkpop.com",
    "variety.com", "hollywoodreporter.com", "deadline.com", "billboard.com", "ew.com", "rollingstone.com",
    "npr.org", "time.com", "nbcnews.com"
]

def extract_claim_and_queries(text):
    prompt = f"""
    วิเคราะห์ข้อความต่อไปนี้: "{text}"

    งานที่ 1: สกัดข้อกล่าวอ้างหลัก (Exact Claim) ระบุให้ชัดเจนว่า ใคร ทำอะไร ที่ไหน เมื่อไหร่ (ภาษาไทย)
    งานที่ 2: สร้างคำค้นหา (Search Queries) เป็น "ภาษาไทย" 2 ประโยคที่ปรับแต่งมาอย่างดีสำหรับ Search Engine

    ตอบกลับเป็น JSON ตามโครงสร้างนี้เท่านั้น:
    {{
        "exact_claim": "สรุปข้อกล่าวอ้างสั้นๆ กระชับ เป็นข้อเท็จจริง",
        "queries": ["คำค้นหาที่ 1", "คำค้นหาที่ 2"]
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
            data.get("queries", [text[:30]]), 
            data.get("exact_claim", "ไม่สามารถวิเคราะห์บริบทได้")
        )
    except:
        return [text[:30]], "ระบบเกิดข้อผิดพลาดในการดึงข้อมูล"

def scrape_full_news(url, ddg_snippet=""):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_text = " ".join([p.get_text(strip=True) for p in paragraphs])
        return full_text[:2000] if full_text else f"ดึงเนื้อหาเต็มไม่ได้ อ้างอิงจากสรุป: {ddg_snippet}"
    except Exception:
        return f"เว็บไซต์ขัดข้อง อ้างอิงจากสรุป: {ddg_snippet}"

def search_trusted_news(queries):
    results = []
    seen_links = set()
    
    try:
        with DDGS() as ddgs:
            for search_q in queries:
                if len(results) >= 3: 
                    break 
                
                print(f"🔍 Searching for: {search_q}")
                search_results = ddgs.text(search_q, region='th-th', safesearch='off', max_results=15)
                
                if search_results:
                    for r in search_results:
                        link = r.get('href', '')
                        if not link or link in seen_links: continue
                        
                        clean_url = link.replace("https://", "").replace("http://", "").replace("www.", "")
                        
                        # เช็คว่าอยู่ในเว็บที่เชื่อถือได้หรือไม่ (ไม่แยกหมวดหมู่)
                        if any(trusted.lower() in clean_url.lower() for trusted in TRUSTED_DOMAINS):
                            seen_links.add(link)
                            
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

def analyze_logic_strict(text, exact_claim, web_data, queries):
    """
    ฟังก์ชันวิเคราะห์ตามกฎใหม่ 3 ข้อ: Real, Fake, หรือ ? (Misleading)
    """
    web_context = ""
    for i, d in enumerate(web_data):
        web_context += f"อ้างอิง {i+1} [{d['domain']}]: {d['title']}\nเนื้อหา: {d['body']}\n\n"

    prompt = f"""
    คุณคือ AI ตรวจสอบข้อเท็จจริง (Fact-checker) 
    นี่คือข้อความต้นฉบับ: "{text}"
    นี่คือข้อกล่าวอ้างที่ต้องการตรวจสอบ: "{exact_claim}"
    
    ข้อมูลอ้างอิงจากเว็บที่เชื่อถือได้ที่ค้นพบ:
    {web_context if web_context else "ไม่มีข้อมูลจากเว็บที่เชื่อถือได้เลย"}

    จงวิเคราะห์ตามกฎ 3 ข้อนี้เท่านั้นอย่างเคร่งครัด:
    
    กฎข้อที่ 1 (Real): ถ้าพบข้อมูลอ้างอิง 1-3 ลิงก์ และ "เนื้อหาเหมือนกันตรงกัน" กับข้อความต้นฉบับแบบชัดเจน ให้ตอบ "real" (credibility_score 0.85-0.99)
    กฎข้อที่ 2 (Fake): ถ้าหาข้อมูลอ้างอิง "ไม่เจอเลย" หรือ "ไม่ตรงเลย" แถมข้อความต้นฉบับมีลักษณะ ชักชวน, หลอกให้หลงเชื่อ, น่าสงสัย, หรือเคลมเกินจริง ให้ตอบ "fake" ทันที (credibility_score 0.01-0.20)
    กฎข้อที่ 3 (Misleading / ?): ถ้าหาข้อมูลอ้างอิงเจอ แต่ข้อความต้นฉบับมีการใช้ "คำที่กระแทกกระทั้น", "พยายามชักชวนให้หลงเชื่อ", "บิดเบือนอารมณ์" (ตามลักษณะข่าวปลอม) ให้ตอบ "misleading" (credibility_score 0.40-0.60)

    ตอบกลับเป็น JSON Format ตามโครงสร้างนี้เท่านั้น:
    {{
        "label": "real หรือ fake หรือ misleading",
        "credibility_score": <float เช่น 0.95, 0.05, 0.50>,
        "reason": "อธิบายสั้นๆ (ภาษาไทย) ว่าทำไมถึงตัดสินแบบนี้ อิงตามกฎข้อใด"
    }}
    """
    
    try:
        res = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a strict fact checker. Output ONLY JSON."}, {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        data = json.loads(res.choices[0].message.content)
        
        label = data.get("label", "fake") # ถ้าพังให้ตี Fake ไว้ก่อน
        score = data.get("credibility_score", 0.0)
        reason = data.get("reason", "ประมวลผลเหตุผลผิดพลาด")
        
        # แมปปิ้งผลลัพธ์ให้แสดงเป็น UI ตามที่คุณต้องการ
        if label == "real":
            ui_result = "✔ Real (เจอข้อมูลยืนยัน)"
        elif label == "fake":
            ui_result = "⚠ Fake (ไม่มีข้อมูล/เข้าข่ายหลอกลวง)"
        elif label == "misleading":
            ui_result = "❓ (ระวัง! ข้อมูลบิดเบือน/ใช้คำชักจูง)"
        else:
            ui_result = "⚠ Fake (ไม่มีข้อมูล/เข้าข่ายหลอกลวง)"
            
        ui_confidence = int(float(score) * 100) 
        
        return ui_result, reason, ui_confidence, queries

    except Exception as e:
        print(f"❌ Analysis Error: {e}")
        return "⚠ Error", f"ระบบ AI ขัดข้อง: {str(e)}", 0, queries

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
        
        # ปรับปรุง: ไม่ใช้ Category แล้ว ใช้คำว่า "Global Search" แทนเพื่อบันทึกลง Database
        category = "Global Search" 
        
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
                    'category': category,
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

        # 1. ดึง Keyword (ไม่แยกหมวดหมู่แล้ว)
        queries, exact_claim = extract_claim_and_queries(news)
        print(f"🧠 AI Exact Claim: {exact_claim}")
        
        # 2. ค้นหาข่าวจากทุกลิงก์
        web_data = search_trusted_news(queries)
        
        # 3. วิเคราะห์ตามกฎเหล็ก 3 ข้อ
        result, reason, confidence, keywords = analyze_logic_strict(news, exact_claim, web_data, queries)
        references = web_data[:4] 

        process_time = round(time.time() - start_time, 2)

        try:
            db_insert = supabase.table("search_history").insert({
                "user_query": news,
                "category": category, # ใส่ Global Search เพื่อให้ฐานข้อมูลไม่พัง
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
            'signals': ["Strict Rule Checked"], 
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