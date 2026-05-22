import requests
import json
import sqlite3
import os
from datetime import datetime
from flask import Flask, request, jsonify

# ========== إعدادات من متغيرات البيئة ==========
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID", "8507370054")

if not TOKEN:
    print("❌ خطأ: TOKEN غير موجود في متغيرات البيئة!")
    exit(1)

URL = f"https://api.telegram.org/bot{TOKEN}/"
app = Flask(__name__)

# ========== إعداد قاعدة البيانات ==========
def init_db():
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    
    # جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_seen TEXT,
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  play_style TEXT DEFAULT 'two_fingers',
                  created_at TEXT)''')
    
    # جدول الإحصائيات
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command TEXT,
                  user_id INTEGER,
                  timestamp TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# ========== البيانات الثابتة ==========
SNIPERS = {
    "awm": {"name": "AWM", "no_gyro": 35, "gyro": 150, "tip": "أقوى قناص في اللعبة"},
    "m24": {"name": "M24", "no_gyro": 40, "gyro": 160, "tip": "سرعة ردة فعل ممتازة"},
    "kar98": {"name": "Kar98k", "no_gyro": 45, "gyro": 170, "tip": "كلاسيكي ومحبوب"}
}

PLAY_STYLES = {
    "one_finger": {"name": "🖐️ إصبع واحد", "sens": 110, "gyro": 400},
    "two_fingers": {"name": "✌️ إصبعين", "sens": 95, "gyro": 330},
    "three_fingers": {"name": "👌 ثلاثة أصابع", "sens": 80, "gyro": 280},
    "four_fingers": {"name": "🖖 أربعة أصابع", "sens": 70, "gyro": 250},
    "claw": {"name": "🦞 Claw", "sens": 65, "gyro": 220}
}

# ========== دوال المساعدة ==========
def send_message(chat_id, text, reply_markup=None):
    """إرسال رسالة إلى تليجرام"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(URL + "sendMessage", json=payload, timeout=5)
        return response.ok
    except Exception as e:
        print(f"خطأ في الإرسال: {e}")
        return False

def save_user(user_id, username, first_name):
    """حفظ المستخدم في قاعدة البيانات"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def save_stats(command, user_id):
    """حفظ إحصائيات الأوامر"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO stats (command, user_id, timestamp) VALUES (?, ?, ?)",
              (command, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ========== لوحة المفاتيح التفاعلية ==========
def get_main_keyboard():
    """لوحة المفاتيح الرئيسية"""
    return {
        "keyboard": [
            [{"text": "🎯 حساسية النار"}, {"text": "🔫 إعدادات القناص"}],
            [{"text": "🖐️ أسلوب اللعب"}, {"text": "🏆 ملفي الشخصي"}],
            [{"text": "📊 الإحصائيات"}, {"text": "❓ مساعدة"}]
        ],
        "resize_keyboard": True,
        "persistent": True
    }

def get_sensitivity_keyboard():
    """أزرار حساسية النار"""
    return {
        "inline_keyboard": [
            [{"text": "🎯 بدون جيروسكوب", "callback_data": "no_gyro"}],
            [{"text": "📳 مع جيروسكوب", "callback_data": "gyro"}],
            [{"text": "🔫 إعدادات القناص", "callback_data": "sniper"}],
            [{"text": "◀️ الرجوع للرئيسية", "callback_data": "back"}]
        ]
    }

# ========== محتوى الرسائل ==========
CONTENT = {
    "start": """🎮 *بوت ببجي المحترف* 🎮

✨ *المميزات:*
• 🎯 إعدادات حساسية متقدمة
• 🔫 إعدادات خاصة للقناصات
• 🖐️ أساليب لعب متنوعة
• 🏆 نظام مستويات وخبرة

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 استخدم الأزرار أدناه للتنقل""",

    "no_gyro": """🎯 *حساسية النار - بدون جيروسكوب*

┌─────────────────────────┐
│ ▪️ ريد دوت / هولو : 95% │
│ ▪️ 2x : 70%             │
│ ▪️ 3x : 60%             │
│ ▪️ 4x : 50%             │
│ ▪️ 6x : 45%             │
└─────────────────────────┘

💡 *نصيحة:* ابدأ بهذه القيم
وعدّل حسب راحتك في التدريب""",

    "gyro": """📳 *حساسية النار - مع جيروسكوب*

┌─────────────────────────┐
│ ▪️ ريد دوت / هولو : 330%│
│ ▪️ 2x : 280%            │
│ ▪️ 3x : 230%            │
│ ▪️ 4x : 180%            │
│ ▪️ 6x : 160%            │
└─────────────────────────┘

💡 *نصيحة:* الجيروسكوب يحسن ثبات الرتكيلة كثيراً"""
}

def get_sniper_content(sniper_key=None):
    """محتوى إعدادات القناص"""
    if sniper_key and sniper_key in SNIPERS:
        s = SNIPERS[sniper_key]
        return f"""🔫 *إعدادات {s['name']}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 بدون جيروسكوب : {s['no_gyro']}%
📳 مع جيروسكوب : {s['gyro']}%
💡 نصيحة : {s['tip']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
/sniper - لعرض جميع القناصات"""
    
    text = "🔫 *إعدادات القناصات*\n\n"
    for k, s in SNIPERS.items():
        text += f"┌ *{s['name']}*\n├ بدون جيروسكوب: {s['no_gyro']}%\n├ مع جيروسكوب: {s['gyro']}%\n└ {s['tip'][:20]}...\n\n"
    text += "📌 استخدم /sniper {الاسم} لتفاصيل أكثر\nمثال: `/sniper awm`"
    return text

def get_play_style_content(style_key=None):
    """محتوى أساليب اللعب"""
    if style_key and style_key in PLAY_STYLES:
        s = PLAY_STYLES[style_key]
        return f"""🖐️ *أسلوب {s['name']}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 حساسية بدون جيروسكوب: {s['sens']}%
📳 حساسية الجيروسكوب: {s['gyro']}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 استخدم `/set_style {style_key}` لتعيين هذا الأسلوب"""
    
    text = "🎮 *أساليب اللعب المتاحة*\n\n"
    for k, s in PLAY_STYLES.items():
        text += f"┌ {s['name']}\n├ حساسية: {s['sens']}%\n└ جيروسكوب: {s['gyro']}%\n\n"
    text += "📌 استخدم `/play_style {الاسم}` لتفاصيل أكثر\nمثال: `/play_style four_fingers`"
    return text

def get_profile_content(user_id):
    """ملف المستخدم الشخصي"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT xp, level, play_style, created_at FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    c.execute("SELECT COUNT(*) FROM stats WHERE user_id = ?", (user_id,))
    commands_count = c.fetchone()[0]
    conn.close()
    
    if not user:
        return "🏆 *ملفك الشخصي*\n\nاستخدم البوت أكثر لظهور إحصائياتك!"
    
    xp, level, play_style, created_at = user
    style_name = PLAY_STYLES.get(play_style, PLAY_STYLES["two_fingers"])["name"]
    
    return f"""🏆 *ملفك الشخصي*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 المستوى: {level}
⭐ الخبرة (XP): {xp}
🖐️ أسلوب اللعب: {style_name}
📝 الأوامر المستخدمة: {commands_count}
📅 عضو منذ: {created_at[:10] if created_at else "جديد"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 استخدم الأوامر لتزيد خبرتك وتفتح مستويات جديدة!"""

def get_stats_content(user_id):
    """إحصائيات المستخدم"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    c.execute("SELECT command, COUNT(*) FROM stats WHERE user_id = ? GROUP BY command ORDER BY COUNT(*) DESC LIMIT 5", (user_id,))
    top = c.fetchall()
    conn.close()
    
    text = f"📊 *إحصائياتك*\n\n📝 إجمالي الأوامر: {total}\n\n🔥 *أكثر الأوامر استخداماً:*\n"
    for cmd, count in top:
        text += f"• {cmd}: {count} مرة\n"
    return text

def set_play_style(user_id, style_key):
    """تعيين أسلوب اللعب للمستخدم"""
    if style_key not in PLAY_STYLES:
        return False
    
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET play_style = ? WHERE user_id = ?", (style_key, user_id))
    conn.commit()
    conn.close()
    return True

def add_xp(user_id, amount=1):
    """إضافة خبرة للمستخدم"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        new_xp = row[0] + amount
        new_level = row[1]
        if new_xp >= new_level * 100:
            new_level = min(new_level + 1, 10)
        c.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
        conn.commit()
        if new_level > row[1]:
            send_message(user_id, f"🎉 *تهانينا!*\n\nرُقيت إلى المستوى {new_level}!")
    conn.close()

# ========== معالجة الأزرار (Callback Query) ==========
def handle_callback(callback_query):
    """معالجة الضغط على الأزرار التفاعلية"""
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query["data"]
    
    # الرد على الضغطة (لإزالة التحميل)
    requests.post(URL + "answerCallbackQuery", json={"callback_query_id": callback_id})
    
    if data == "no_gyro":
        send_message(chat_id, CONTENT["no_gyro"])
    
    elif data == "gyro":
        send_message(chat_id, CONTENT["gyro"])
    
    elif data == "sniper":
        send_message(chat_id, get_sniper_content())
    
    elif data == "back":
        send_message(chat_id, CONTENT["start"], get_main_keyboard())

# ========== معالجة الأزرار النصية والأوامر ==========
def handle_message(chat_id, text, username=None, first_name=None):
    """معالجة الرسائل الواردة"""
    save_user(chat_id, username, first_name)
    save_stats(text, chat_id)
    add_xp(chat_id)
    
    # الأزرار النصية (من لوحة المفاتيح الرئيسية)
    if text == "🎯 حساسية النار":
        send_message(chat_id, "اختر نوع الحساسية:", get_sensitivity_keyboard())
    elif text == "🔫 إعدادات القناص":
        send_message(chat_id, get_sniper_content())
    elif text == "🖐️ أسلوب اللعب":
        send_message(chat_id, get_play_style_content())
    elif text == "🏆 ملفي الشخصي":
        send_message(chat_id, get_profile_content(chat_id))
    elif text == "📊 الإحصائيات":
        send_message(chat_id, get_stats_content(chat_id))
    elif text == "❓ مساعدة":
        send_message(chat_id, get_help_content())
    
    # الأوامر النصية
    elif text == "/start":
        send_message(chat_id, CONTENT["start"], get_main_keyboard())
    
    elif text == "/help":
        send_message(chat_id, get_help_content())
    
    elif text == "/no_gyro":
        send_message(chat_id, CONTENT["no_gyro"])
    
    elif text == "/gyro":
        send_message(chat_id, CONTENT["gyro"])
    
    elif text == "/sniper":
        send_message(chat_id, get_sniper_content())
    
    elif text == "/play_style":
        send_message(chat_id, get_play_style_content())
    
    elif text == "/profile":
        send_message(chat_id, get_profile_content(chat_id))
    
    elif text == "/stats":
        send_message(chat_id, get_stats_content(chat_id))
    
    elif text.startswith("/sniper "):
        sniper_key = text.split()[1].lower()
        send_message(chat_id, get_sniper_content(sniper_key))
    
    elif text.startswith("/play_style "):
        style_key = text.split()[1].lower()
        send_message(chat_id, get_play_style_content(style_key))
    
    elif text.startswith("/set_style "):
        style_key = text.split()[1].lower()
        if set_play_style(chat_id, style_key):
            send_message(chat_id, f"✅ تم تعيين أسلوب {PLAY_STYLES[style_key]['name']}")
        else:
            send_message(chat_id, f"❌ أسلوب '{style_key}' غير موجود")
    
    else:
        send_message(chat_id, "❓ أمر غير معروف.\nأرسل /help أو استخدم الأزرار أدناه", get_main_keyboard())

def get_help_content():
    return """📖 *قائمة الأوامر الكاملة*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *الحساسية:*
/no_gyro - بدون جيروسكوب
/gyro - مع جيروسكوب

🔫 *القناصات:*
/sniper - جميع القناصات
/sniper awm - إعدادات AWM

🖐️ *أساليب اللعب:*
/play_style - جميع الأساليب
/play_style four_fingers - تفاصيل أسلوب
/set_style four_fingers - تعيين أسلوبك

🏆 *المستخدم:*
/profile - ملفك الشخصي
/stats - إحصائياتك

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *نصيحة:* استخدم الأزرار للتنقل السريع!"""

# ========== Webhook Endpoints ==========
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """نقطة نهاية الـ Webhook - تستقبل التحديثات من تليجرام"""
    try:
        update = request.get_json()
        
        if not update:
            return "No update", 400
        
        # معالجة الضغط على الأزرار التفاعلية (Inline Keyboard)
        if "callback_query" in update:
            handle_callback(update["callback_query"])
        
        # معالجة الرسائل النصية
        elif "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            username = msg["chat"].get("username")
            first_name = msg["chat"].get("first_name")
            
            # معالجة سريعة بدون threads
            handle_message(chat_id, text, username, first_name)
        
        return "ok", 200
    
    except Exception as e:
        print(f"خطأ في الـ Webhook: {e}")
        return "error", 500

@app.route("/healthz")
def healthz():
    """فحص صحة الخدمة - مهم لـ Render"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()}), 200

@app.route("/")
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        "bot": "PUBG Sensitivity Bot",
        "status": "running",
        "version": "2.0.0"
    }), 200

# ========== تشغيل التطبيق ==========
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 تشغيل بوت ببجي المحترف")
    print("=" * 50)
    print(f"✅ التوكن: {TOKEN[:15]}...")
    print(f"👑 المدير: {ADMIN_ID}")
    print("📡 Webhook جاهز للاستقبال")
    print("=" * 50)
    
    # تشغيل الخادم
    app.run(host="0.0.0.0", port=5000, threaded=True)
