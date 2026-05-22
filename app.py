import requests
import json
import sqlite3
import threading
import time
import os
from datetime import datetime
from flask import Flask, request

# ========== إعداداتك الشخصية (من متغيرات البيئة) ==========
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID", "8507370054")

if not TOKEN:
    print("❌ خطأ: TOKEN غير موجود في متغيرات البيئة!")
    exit(1)

URL = f"https://api.telegram.org/bot{8745230533:AAHuqoopmH3JhFX1_DSG-yolAGR-txB0zQ0}/"
app = Flask(__name__)

# ========== إعداد قاعدة البيانات ==========
def init_db():
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_seen TEXT,
                  preferences TEXT,
                  notification_enabled INTEGER DEFAULT 1,
                  theme TEXT DEFAULT 'light',
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  play_style TEXT DEFAULT 'two_fingers')''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (command TEXT,
                  user_id INTEGER,
                  timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS saved_sensitivities
                 (user_id INTEGER,
                  preset_name TEXT,
                  sensitivity_data TEXT,
                  created_at TEXT,
                  PRIMARY KEY (user_id, preset_name))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS achievements
                 (user_id INTEGER,
                  achievement_name TEXT,
                  unlocked_at TEXT,
                  PRIMARY KEY (user_id, achievement_name))''')
    
    conn.commit()
    conn.close()

init_db()

# ========== المحتوى ==========
def get_start_message():
    return """🎮 *بوت ببجي المتكامل* 🎮

✨ *المميزات:*

🎯 /sensitivity - إعدادات الحساسية
🔫 /sniper - إعدادات القناصات
🖐️ /play_style - أساليب اللعب
🏆 /profile - ملفك الشخصي
📊 /stats - إحصائياتك

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 أرسل /help لجميع الأوامر
"""

def get_help():
    return """📖 *قائمة الأوامر*

/sensitivity_full - جميع إعدادات الحساسية
/no_gyro - حساسية بدون جيروسكوب
/gyro - حساسية مع جيروسكوب
/sniper - إعدادات القناصات
/play_style - أساليب اللعب
/profile - ملفك الشخصي
/stats - إحصائياتك
/start - الترحيب
/help - هذه المساعدة
"""

def get_no_gyro():
    return "🎯 *بدون جيروسكوب*\n\nريد دوت: 95%\n2x: 70%\n3x: 60%\n4x: 50%\n6x: 45%"

def get_gyro():
    return "📳 *مع جيروسكوب*\n\nريد دوت: 330%\n2x: 280%\n3x: 230%\n4x: 180%\n6x: 160%"

def get_sniper():
    return """🔫 *إعدادات القناصات*

AWM: 35% (بدون جيروسكوب) | 150% (مع جيروسكوب)
M24: 40% | 160%
Kar98k: 45% | 170%
Mosin: 45% | 170%

💡 استخدم /sniper awm لتفاصيل أكثر"""

def get_play_styles():
    return """🎮 *أساليب اللعب*

🖐️ إصبع واحد: حساسية 110% | جيروسكوب 400%
✌️ إصبعين: 95% | 330%
👌 ثلاثة أصابع: 80% | 280%
🖖 أربعة أصابع: 70% | 250%
🦞 Claw: 65% | 220%

📌 استخدم /set_style {اسم} لتعيين أسلوبك"""

# ========== دوال التليجرام ==========
def send_message(chat_id, text):
    try:
        requests.post(URL + "sendMessage", 
                     json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                     timeout=10)
    except Exception as e:
        print(f"خطأ في الإرسال: {e}")

def save_user(user_id, username, first_name):
    try:
        conn = sqlite3.connect('pubg_bot.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_seen) VALUES (?, ?, ?, ?)",
                  (user_id, username, first_name, datetime.now().isoformat()))
        c.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
    except:
        pass

def save_stats(command, user_id):
    try:
        conn = sqlite3.connect('pubg_bot.db')
        c = conn.cursor()
        c.execute("INSERT INTO stats (command, user_id, timestamp) VALUES (?, ?, ?)",
                  (command, user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

# ========== معالجة الرسائل ==========
def handle_message(chat_id, text, username=None, first_name=None):
    save_user(chat_id, username, first_name)
    save_stats(text, chat_id)
    
    if text == "/start":
        send_message(chat_id, get_start_message())
    elif text == "/help":
        send_message(chat_id, get_help())
    elif text == "/sensitivity_full":
        send_message(chat_id, get_no_gyro() + "\n\n" + get_gyro())
    elif text == "/no_gyro":
        send_message(chat_id, get_no_gyro())
    elif text == "/gyro":
        send_message(chat_id, get_gyro())
    elif text == "/sniper":
        send_message(chat_id, get_sniper())
    elif text == "/play_style":
        send_message(chat_id, get_play_styles())
    elif text == "/profile":
        send_message(chat_id, "🏆 *ملفك الشخصي*\n\nمستواك: برونزي\nXP: 0\nاستخدم الأوامر لتكسب XP!")
    elif text == "/stats":
        send_message(chat_id, "📊 *إحصائياتك*\n\nعدد الأوامر: قيد التسجيل\nاستمر في استخدام البوت!")
    else:
        send_message(chat_id, "❓ أمر غير معروف. أرسل /help")

# ==========端点 Flask ==========
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if update and "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            username = msg["chat"].get("username")
            first_name = msg["chat"].get("first_name")
            threading.Thread(target=handle_message, args=(chat_id, text, username, first_name)).start()
    except Exception as e:
        print(f"خطأ: {e}")
    return "ok", 200

# ✅ مهم جداً: إضافة مسار /healthz لفحص الصحة
@app.route("/healthz")
def healthz():
    return "OK", 200

@app.route("/")
def home():
    return "✅ بوت ببجي يعمل بنجاح!", 200

# ========== التشغيل ==========
if __name__ == "__main__":
    print("🚀 تشغيل بوت ببجي...")
    print(f"✅ التوكن: {TOKEN[:10]}...")
    print("📡 استمع على http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000)
