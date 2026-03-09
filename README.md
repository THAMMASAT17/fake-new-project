# AI Fake News Scanner

AI Fake News Scanner เป็นระบบที่ช่วยผู้ใช้ตรวจสอบข่าวที่น่าสงสัย โดยใช้ AI วิเคราะห์เนื้อหาข่าวและค้นหาแหล่งข่าวที่น่าเชื่อถือ เพื่อประเมินว่าข่าวนั้นมีแนวโน้มเป็นข่าวจริง ข้อมูลที่ทำให้เข้าใจผิด หรือข่าวปลอม

ระบบถูกออกแบบเพื่อช่วยลดเวลาในการตรวจสอบข่าวของผู้ใช้ และช่วยให้ผู้ใช้สามารถตัดสินใจได้ดีขึ้นก่อนแชร์ข้อมูลบนโซเชียลมีเดีย

---

# Features

- วิเคราะห์ข้อความข่าวด้วย AI
- แสดงผลลัพธ์ เช่น  
  - Likely Real  
  - Fake News Risk  
  - Possibly Misleading  
  - Insufficient Data
- แสดงแหล่งข่าวที่ใช้ในการวิเคราะห์
- ผู้ใช้สามารถตรวจสอบแหล่งข่าวด้วยตนเอง
- มีระบบ feedback เพื่อปรับปรุงความแม่นยำของระบบ

---

# Tech Stack

Frontend
- HTML
- CSS

Backend
- Python (Flask)

Libraries
- BeautifulSoup4
- Requests
- python-dotenv

AI Model
- Groq API

---

# Project Structure

fake-new-project
│
├── app.py
├── requirements.txt
├── templates
│ └── index.html
├── static
├── .env
└── README.md

---

# How to Run (วิธีการรันระบบ)

1. Clone repository
git clone <repo-url>

2. เข้าโฟลเดอร์โปรเจกต์
cd fake-new-project

3. ติดตั้ง dependencies
pip install -r requirements.txt

4. สร้างไฟล์ `.env` และเพิ่ม API key
GROQ_API_KEY=your_api_key_here

5. รันระบบ
python app.py

6. เปิดเว็บไซต์ใน browser
http://127.0.0.1:5000

---

# AI Tools Used

โปรเจกต์นี้ใช้เครื่องมือ AI เพื่อช่วยในการพัฒนา เช่น

- **ChatGPT**  
  ใช้ช่วยออกแบบ workflow ของระบบ และช่วยเขียนโค้ดบางส่วน

- **Google Gemini**  
  ใช้ช่วยวิเคราะห์แนวทางการพัฒนาและช่วยปรับปรุงโค้ด
AI ถูกใช้เพื่อช่วยในการพัฒนาเท่านั้น โดยนักพัฒนาเป็นผู้ตรวจสอบและปรับปรุงโค้ดก่อนใช้งานจริง

---

# Source Code
Source code ของระบบประกอบด้วย
- Backend API ที่พัฒนาโดยใช้ Python Flask
- Frontend หน้าเว็บสำหรับรับ input จากผู้ใช้
- ระบบเชื่อมต่อ AI เพื่อวิเคราะห์ข้อความข่าว
- ระบบดึงข้อมูลจากแหล่งข่าวเพื่อใช้เป็นข้อมูลประกอบการวิเคราะห์
