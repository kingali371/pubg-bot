import requests
import json
import sqlite3
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify

# ========== إعدادات التسجيل ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== إعدادات من متغيرات البيئة ==========
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8507370054"))

if not TOKEN:
    logger.error("❌ TOKEN غير موجود في متغيرات البيئة!")
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
                  created_at TEXT,
                  blocked INTEGER DEFAULT 0)''')
    
    # جدول الإحصائيات
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  command TEXT,
                  user_id INTEGER,
                  timestamp TEXT)''')
    
    # جدول الرسائل
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_user INTEGER,
                  to_user INTEGER,
                  message TEXT,
                  timestamp TEXT,
                  is_read INTEGER DEFAULT 0,
                  is_replied INTEGER DEFAULT 0)''')
    
    # جدول الإشعارات
    c.execute('''CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  message TEXT,
                  timestamp TEXT,
                  is_sent INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()
    logger.info("✅ قاعدة البيانات جاهزة")

init_db()

# ========== دوال التواصل ==========
def save_message(from_user, to_user, message):
    """حفظ رسالة في قاعدة البيانات"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user, to_user, message, timestamp) VALUES (?, ?, ?, ?)",
              (from_user, to_user, message, datetime.now().isoformat()))
    msg_id = c.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"📨 رسالة محفوظة: {from_user} → {to_user}")
    return msg_id

def get_unread_messages(user_id):
    """الحصول على الرسائل غير المقروءة"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("""SELECT id, from_user, message, timestamp 
                 FROM messages 
                 WHERE to_user = ? AND is_read = 0 
                 ORDER BY timestamp ASC""", (user_id,))
    messages = c.fetchall()
    conn.close()
    return messages

def mark_as_read(message_ids):
    """تحديد الرسائل كمقروءة"""
    if not message_ids:
        return
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    for msg_id in message_ids:
        c.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    logger.info(f"✅ تم تحديد {len(message_ids)} رسائل كمقروءة")

def mark_as_replied(message_id):
    """تحديد رسالة تم الرد عليها"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("UPDATE messages SET is_replied = 1 WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

def get_conversation(user1, user2, limit=50):
    """الحصول على محادثة بين مستخدمين"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("""SELECT from_user, message, timestamp, is_replied 
                 FROM messages 
                 WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                 ORDER BY timestamp ASC LIMIT ?""",
              (user1, user2, user2, user1, limit))
    messages = c.fetchall()
    conn.close()
    return messages

def save_notification(user_id, message):
    """حفظ إشعار للمستخدم"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO notifications (user_id, message, timestamp) VALUES (?, ?, ?)",
              (user_id, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ========== دوال الإرسال ==========
def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """إرسال رسالة إلى تليجرام"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    try:
        response = requests.post(URL + "sendMessage", json=payload, timeout=10)
        if response.ok:
            logger.info(f"✅ رسالة أرسلت إلى {chat_id}")
            return True
        else:
            logger.error(f"❌ فشل الإرسال: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ في الإرسال: {e}")
        return False

def forward_to_admin(user_id, username, first_name, message):
    """إرسال رسالة المستخدم إلى المدير"""
    # حفظ الرسالة
    msg_id = save_message(user_id, ADMIN_ID, message)
    
    # نص الرسالة للمدير
    admin_text = f"""📨 *رسالة جديدة من مستخدم*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 *المستخدم:* `{user_id}`
📝 *الاسم:* {username or first_name or 'غير معروف'}
🕐 *الوقت:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 *الرسالة:*
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 *للرد:*
/reply_{user_id} نص الرد

أو استخدم الأمر: /reply {user_id} نص الرد"""
    
    # إرسال للمدير
    send_message(ADMIN_ID, admin_text)
    
    # إرسال إشعار صوتي (نصي)
    send_message(ADMIN_ID, f"🔔 *تنبيه:* لديك رسالة جديدة من المستخدم {user_id}")

def forward_to_user(user_id, message, original_msg_id=None):
    """إرسال رد المدير إلى المستخدم"""
    # حفظ الرد
    save_message(ADMIN_ID, user_id, message)
    if original_msg_id:
        mark_as_replied(original_msg_id)
    
    # نص الرد للمستخدم
    user_text = f"""📨 *رد من الدعم الفني*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 *الرد:*
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *ملاحظة:* يمكنك الرد مباشرة على هذه الرسالة"""
    
    # إرسال للمستخدم
    if send_message(user_id, user_text):
        # إشعار للمدير بنجاح الإرسال
        send_message(ADMIN_ID, f"✅ تم إرسال الرد إلى المستخدم {user_id}")
        return True
    else:
        send_message(ADMIN_ID, f"❌ فشل إرسال الرد إلى المستخدم {user_id}")
        return False

def broadcast_to_all(message, admin_id):
    """إرسال رسالة لجميع المستخدمين"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE blocked = 0")
    users = c.fetchall()
    conn.close()
    
    success_count = 0
    fail_count = 0
    
    for (user_id,) in users:
        if send_message(user_id, f"📢 *إشعار من الإدارة*\n\n{message}"):
            success_count += 1
        else:
            fail_count += 1
    
    send_message(admin_id, f"✅ تم إرسال الإشعار إلى {success_count} مستخدم\n❌ فشل الإرسال إلى {fail_count} مستخدم")

# ========== دوال المستخدم ==========
def save_user(user_id, username, first_name):
    """حفظ المستخدم في قاعدة البيانات"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute("UPDATE users SET last_seen = ?, username = ?, first_name = ? WHERE user_id = ?",
              (datetime.now().isoformat(), username, first_name, user_id))
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
    add_xp(user_id)

def add_xp(user_id, amount=1):
    """إضافة خبرة للمستخدم"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        new_xp = row[0] + amount
        new_level = row[1]
        if new_xp >= new_level * 100 and new_level < 10:
            new_level = min(new_level + 1, 10)
            send_message(user_id, f"🎉 *تهانينا!*\n\nرُقيت إلى المستوى {new_level}!")
        c.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
        conn.commit()
    conn.close()

def block_user(admin_id, user_id):
    """حظر مستخدم (للمدير فقط)"""
    if admin_id != ADMIN_ID:
        return False
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

def unblock_user(admin_id, user_id):
    """إلغاء حظر مستخدم (للمدير فقط)"""
    if admin_id != ADMIN_ID:
        return False
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET blocked = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

# ========== لوحات المفاتيح ==========
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "🎯 حساسية النار"}, {"text": "🔫 إعدادات القناص"}],
            [{"text": "🖐️ أسلوب اللعب"}, {"text": "🏆 ملفي الشخصي"}],
            [{"text": "📊 الإحصائيات"}, {"text": "📞 تواصل مع الدعم"}],
            [{"text": "❓ مساعدة"}]
        ],
        "resize_keyboard": True,
        "persistent": True
    }

def get_sensitivity_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🎯 بدون جيروسكوب", "callback_data": "no_gyro"}],
            [{"text": "📳 مع جيروسكوب", "callback_data": "gyro"}],
            [{"text": "🔫 إعدادات القناص", "callback_data": "sniper"}],
            [{"text": "📞 تواصل مع الدعم", "callback_data": "contact"}],
            [{"text": "◀️ الرجوع", "callback_data": "back"}]
        ]
    }

def get_admin_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📨 رسائل غير مقروءة", "callback_data": "admin_unread"}],
            [{"text": "📊 إحصائيات البوت", "callback_data": "admin_stats"}],
            [{"text": "📢 إشعار للجميع", "callback_data": "admin_broadcast"}],
            [{"text": "👥 قائمة المستخدمين", "callback_data": "admin_users"}],
            [{"text": "💬 محادثاتي", "callback_data": "admin_conversations"}]
        ]
    }

def get_contact_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✍️ كتابة رسالة جديدة", "callback_data": "new_message"}],
            [{"text": "📋 رسائلي السابقة", "callback_data": "my_messages"}],
            [{"text": "◀️ رجوع", "callback_data": "back"}]
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
• 📞 تواصل مباشر مع الدعم

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 استخدم الأزرار أدناه للتنقل""",

    "contact": """📞 *مركز التواصل مع الدعم*

يمكنك التواصل مع فريق الدعم لأي استفسار أو اقتراح.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *طرق التواصل:*

1️⃣ *إرسال رسالة جديدة*
   اضغط على الزر أدناه واكتب رسالتك

2️⃣ *الرد على رسالة سابقة*
   اكتب ردك مباشرة على رسالة الدعم

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ *وقت الرد:* خلال 24 ساعة
💙 *شكراً لتواصلك معنا*"""

}

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

def get_sniper_content(sniper_key=None):
    if sniper_key and sniper_key in SNIPERS:
        s = SNIPERS[sniper_key]
        return f"""🔫 *إعدادات {s['name']}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 بدون جيروسكوب : {s['no_gyro']}%
📳 مع جيروسكوب : {s['gyro']}%
💡 نصيحة : {s['tip']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
    
    text = "🔫 *إعدادات القناصات*\n\n"
    for k, s in SNIPERS.items():
        text += f"┌ *{s['name']}*\n├ بدون جيروسكوب: {s['no_gyro']}%\n├ مع جيروسكوب: {s['gyro']}%\n└ {s['tip']}\n\n"
    return text

def get_play_style_content(style_key=None):
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
    return text

def get_profile_content(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT xp, level, play_style, created_at FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    c.execute("SELECT COUNT(*) FROM stats WHERE user_id = ?", (user_id,))
    commands_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages WHERE from_user = ? AND to_user = ?", (user_id, ADMIN_ID))
    sent_messages = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages WHERE to_user = ? AND from_user = ?", (user_id, ADMIN_ID))
    received_messages = c.fetchone()[0]
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
📝 الأوامر: {commands_count}
📤 رسائل أرسلتها: {sent_messages}
📥 رسائل استلمتها: {received_messages}
📅 عضو منذ: {created_at[:10] if created_at else "جديد"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

def get_stats_content(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    c.execute("SELECT command, COUNT(*) FROM stats WHERE user_id = ? GROUP BY command ORDER BY COUNT(*) DESC LIMIT 5", (user_id,))
    top = c.fetchall()
    conn.close()
    
    text = f"📊 *إحصائياتك*\n\n📝 إجمالي الأوامر: {total}\n\n🔥 *الأكثر استخداماً:*\n"
    for cmd, count in top:
        text += f"• `{cmd}`: {count} مرة\n"
    return text

def get_help_content():
    return """📖 *قائمة الأوامر الكاملة*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *الحساسية:*
/no_gyro - بدون جيروسكوب
/gyro - مع جيروسكوب

🔫 *القناصات:*
/sniper - جميع القناصات

🖐️ *أساليب اللعب:*
/play_style - جميع الأساليب
/set_style - تعيين أسلوبك

🏆 *المستخدم:*
/profile - ملفك الشخصي
/stats - إحصائياتك

📞 *التواصل:*
/contact - تواصل مع الدعم
(أرسل أي رسالة للدعم)

━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

def set_play_style(user_id, style_key):
    if style_key not in PLAY_STYLES:
        return False
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET play_style = ? WHERE user_id = ?", (style_key, user_id))
    conn.commit()
    conn.close()
    return True

def get_my_messages(user_id):
    """الحصول على رسائل المستخدم مع الدعم"""
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("""SELECT id, from_user, message, timestamp, is_replied 
                 FROM messages 
                 WHERE (from_user = ? OR to_user = ?) 
                 ORDER BY timestamp DESC LIMIT 20""", (user_id, user_id))
    messages = c.fetchall()
    conn.close()
    
    if not messages:
        return "📭 لا توجد رسائل سابقة"
    
    text = "📋 *رسائلي السابقة*\n\n"
    for msg_id, from_user, message, timestamp, is_replied in messages:
        if from_user == user_id:
            status = "✅ تم الرد" if is_replied else "⏳ قيد الانتظار"
            text += f"📤 *إليك:* {message[:50]}\n   🕐 {timestamp[:16]} | {status}\n\n"
        else:
            text += f"📥 *من الدعم:* {message[:50]}\n   🕐 {timestamp[:16]}\n\n"
    return text

# ========== أوامر المدير ==========
def handle_admin_command(user_id, text):
    if user_id != ADMIN_ID:
        send_message(user_id, "⛔ هذا الأمر مخصص للمدير فقط")
        return
    
    # أمر الرد المباشر
    if text.startswith("/reply_"):
        parts = text.split("_", 1)
        if len(parts) == 2:
            try:
                target_user = int(parts[1].split()[0])
                reply_message = " ".join(parts[1].split()[1:])
                if reply_message:
                    forward_to_user(target_user, reply_message)
                else:
                    send_message(ADMIN_ID, "❌ أضف نص الرد بعد المعرف")
            except ValueError:
                send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")
        return
    
    if text.startswith("/reply "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            try:
                target_user = int(parts[1])
                reply_message = parts[2]
                forward_to_user(target_user, reply_message)
            except ValueError:
                send_message(ADMIN_ID, "❌ معرف المستخدم غير صحيح")
        else:
            send_message(ADMIN_ID, "❌ استخدم: `/reply {معرف_المستخدم} {رسالتك}`")
    
    elif text.startswith("/broadcast "):
        message = text[11:]
        broadcast_to_all(message, ADMIN_ID)
    
    elif text == "/admin":
        send_message(ADMIN_ID, "👑 *لوحة تحكم المدير*\n\nاختر من الأزرار أدناه:", get_admin_keyboard())
    
    elif text == "/unread":
        messages = get_unread_messages(ADMIN_ID)
        if messages:
            msg_text = "📨 *رسائل غير مقروءة:*\n\n"
            for msg_id, from_user, msg_message, timestamp in messages[:10]:
                msg_text += f"👤 من: `{from_user}`\n💬 {msg_message[:100]}\n🕐 {timestamp[:16]}\n/reply_{from_user} ردك\n━━━━━━━━━━━\n"
            send_message(ADMIN_ID, msg_text)
            mark_as_read([m[0] for m in messages])
        else:
            send_message(ADMIN_ID, "📭 لا توجد رسائل غير مقروءة")
    
    elif text == "/stats_all":
        conn = sqlite3.connect('pubg_bot.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM stats")
        commands_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages")
        messages_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0 AND to_user = ?", (ADMIN_ID,))
        unread_count = c.fetchone()[0]
        conn.close()
        
        stats_text = f"""📊 *إحصائيات البوت*

👥 المستخدمين: {users_count}
📝 الأوامر: {commands_count}
💬 الرسائل: {messages_count}
📨 غير مقروء: {unread_count}
🚀 الحالة: يعمل ✅"""
        send_message(ADMIN_ID, stats_text)

# ========== معالجة الأزرار ==========
def handle_callback(callback_query):
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query["data"]
    
    # الرد على الضغطة
    requests.post(URL + "answerCallbackQuery", json={"callback_query_id": callback_id})
    
    # أوامر المدير
    if data.startswith("admin_"):
        if chat_id != ADMIN_ID:
            send_message(chat_id, "⛔ هذا الزر للمدير فقط")
            return
        
        if data == "admin_unread":
            messages = get_unread_messages(ADMIN_ID)
            if messages:
                text = "📨 *رسائل غير مقروءة:*\n\n"
                for msg_id, from_user, msg_message, timestamp in messages[:10]:
                    text += f"👤 من: `{from_user}`\n💬 {msg_message[:100]}\n🕐 {timestamp[:16]}\n/reply_{from_user} ردك\n━━━━━━━━━━━\n"
                send_message(ADMIN_ID, text)
                mark_as_read([m[0] for m in messages])
            else:
                send_message(ADMIN_ID, "📭 لا توجد رسائل غير مقروءة")
        
        elif data == "admin_stats":
            conn = sqlite3.connect('pubg_bot.db')
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM messages")
            messages = c.fetchone()[0]
            conn.close()
            send_message(ADMIN_ID, f"📊 *إحصائيات*\n👥 مستخدمين: {users}\n💬 رسائل: {messages}")
        
        elif data == "admin_broadcast":
            send_message(ADMIN_ID, "📢 *إرسال إشعار للجميع*\n\nأرسل الرسالة بهذا الشكل:\n`/broadcast نص الرسالة`")
        
        elif data == "admin_users":
            conn = sqlite3.connect('pubg_bot.db')
            c = conn.cursor()
            c.execute("SELECT user_id, username, xp, level FROM users ORDER BY xp DESC LIMIT 20")
            users = c.fetchall()
            conn.close()
            text = "👥 *قائمة المستخدمين*\n\n"
            for uid, username, xp, level in users:
                name = username or str(uid)
                text += f"• `{uid}` - {name[:15]} (مستوى {level})\n"
            send_message(ADMIN_ID, text)
        
        elif data == "admin_conversations":
            conn = sqlite3.connect('pubg_bot.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT from_user FROM messages WHERE to_user = ? UNION SELECT DISTINCT to_user FROM messages WHERE from_user = ?", (ADMIN_ID, ADMIN_ID))
            users = c.fetchall()
            conn.close()
            text = "💬 *المحادثات النشطة*\n\n"
            for (uid,) in users:
                if uid != ADMIN_ID:
                    text += f"• `{uid}` - /reply_{uid} للرد\n"
            send_message(ADMIN_ID, text)
    
    # الأزرار العادية
    elif data == "no_gyro":
        send_message(chat_id, "🎯 *بدون جيروسكوب*\n\nريد دوت: 95%\n2x: 70%\n3x: 60%\n4x: 50%\n6x: 45%")
    elif data == "gyro":
        send_message(chat_id, "📳 *مع جيروسكوب*\n\nريد دوت: 330%\n2x: 280%\n3x: 230%\n4x: 180%\n6x: 160%")
    elif data == "sniper":
        send_message(chat_id, get_sniper_content())
    elif data == "contact":
        send_message(chat_id, CONTENT["contact"], get_contact_keyboard())
    elif data == "new_message":
        send_message(chat_id, "✍️ *أكتب رسالتك*\n\nأرسل رسالتك الآن وسيتم إرسالها للدعم.")
    elif data == "my_messages":
        send_message(chat_id, get_my_messages(chat_id))
    elif data == "back":
        send_message(chat_id, CONTENT["start"], get_main_keyboard())

# ========== المعالجة الرئيسية ==========
def handle_message(chat_id, text, username=None, first_name=None):
    # التحقق من الحظر
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT blocked FROM users WHERE user_id = ?", (chat_id,))
    blocked = c.fetchone()
    conn.close()
    
    if blocked and blocked[0] == 1 and chat_id != ADMIN_ID:
        send_message(chat_id, "⛔ تم حظرك من استخدام هذا البوت")
        return
    
    save_user(chat_id, username, first_name)
    save_stats(text, chat_id)
    
    # الأزرار النصية
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
    elif text == "📞 تواصل مع الدعم":
        send_message(chat_id, CONTENT["contact"], get_contact_keyboard())
    elif text == "❓ مساعدة":
        send_message(chat_id, get_help_content())
    
    # الأوامر
    elif text == "/start":
        send_message(chat_id, CONTENT["start"], get_main_keyboard())
    elif text == "/help":
        send_message(chat_id, get_help_content())
    elif text == "/contact":
        send_message(chat_id, CONTENT["contact"], get_contact_keyboard())
    elif text == "/no_gyro":
        send_message(chat_id, "🎯 *بدون جيروسكوب*\n\nريد دوت: 95%\n2x: 70%\n3x: 60%\n4x: 50%\n6x: 45%")
    elif text == "/gyro":
        send_message(chat_id, "📳 *مع جيروسكوب*\n\nريد دوت: 330%\n2x: 280%\n3x: 230%\n4x: 180%\n6x: 160%")
    elif text == "/sniper":
        send_message(chat_id, get_sniper_content())
    elif text == "/play_style":
        send_message(chat_id, get_play_style_content())
    elif text == "/profile":
        send_message(chat_id, get_profile_content(chat_id))
    elif text == "/stats":
        send_message(chat_id, get_stats_content(chat_id))
    
    # أوامر المدير
    elif text.startswith("/reply") or text.startswith("/reply_") or text == "/admin" or text == "/unread" or text == "/stats_all" or text.startswith("/broadcast"):
        handle_admin_command(chat_id, text)
    
    # أوامر أخرى
    elif text.startswith("/set_style "):
        style_key = text.split()[1].lower()
        if set_play_style(chat_id, style_key):
            send_message(chat_id, f"✅ تم تعيين أسلوب {PLAY_STYLES[style_key]['name']}")
        else:
            send_message(chat_id, f"❌ أسلوب '{style_key}' غير موجود")
    
    # رسائل عادية ← إرسال للدعم
    elif not text.startswith("/"):
        # التحقق من عدم إرسال رسالة فارغة
        if len(text.strip()) > 0:
            forward_to_admin(chat_id, username, first_name, text)
            send_message(chat_id, "✅ *تم إرسال رسالتك بنجاح!*\n\nسيتم الرد عليك في أقرب وقت.\nشكراً لتواصلك معنا 💙")
        else:
            send_message(chat_id, "📝 الرجاء كتابة رسالتك قبل الإرسال")
    
    else:
        send_message(chat_id, "❓ أمر غير معروف.\nأرسل /help أو استخدم الأزرار", get_main_keyboard())

# ========== Webhook ==========
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """نقطة نهاية Webhook - تستقبل التحديثات"""
    try:
        update = request.get_json()
        
        if not update:
            return jsonify({"status": "no update"}), 400
        
        logger.info(f"📥 استقبال تحديث: {update.get('update_id', 'unknown')}")
        
        # معالجة الضغط على الأزرار
        if "callback_query" in update:
            handle_callback(update["callback_query"])
        
        # معالجة الرسائل
        elif "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            username = msg["chat"].get("username")
            first_name = msg["chat"].get("first_name")
            
            handle_message(chat_id, text, username, first_name)
        
        return jsonify({"status": "ok"}), 200
    
    except Exception as e:
        logger.error(f"❌ خطأ في Webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/healthz")
def healthz():
    """فحص صحة الخدمة لـ Render"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "bot": "PUBG Bot with Support"
    }), 200

@app.route("/")
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        "bot": "PUBG Sensitivity Bot",
        "version": "3.0.0",
        "features": ["sensitivity", "sniper", "play_styles", "support", "admin_panel"],
        "status": "running"
    }), 200

# ========== التشغيل ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 تشغيل بوت ببجي المتكامل مع نظام التواصل")
    print("=" * 60)
    print(f"✅ التوكن: {TOKEN[:20]}...")
    print(f"👑 المدير: {ADMIN_ID}")
    print("📞 نظام التواصل: مفعل")
    print("🎨 الأزرار التفاعلية: مفعلة")
    print("📊 قاعدة البيانات: جاهزة")
    print("=" * 60)
    print("🌐 Webhook جاهز للاستقبال على:")
    print(f"   POST /{TOKEN}")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5000, threaded=True)
