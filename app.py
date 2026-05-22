import requests
import json
import sqlite3
import threading
import time
from datetime import datetime
from flask import Flask, request

# ========== إعداداتك الشخصية ==========
TOKEN = "ضع_التوكن_هنا"
ADMIN_ID = "ضع_معرف_المالك_هنا"
# ====================================

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
                  preferences TEXT,
                  notification_enabled INTEGER DEFAULT 1,
                  theme TEXT DEFAULT 'light',
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1,
                  play_style TEXT DEFAULT 'two_fingers',
                  language TEXT DEFAULT 'ar')''')
    
    # جدول الإحصائيات
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (command TEXT,
                  user_id INTEGER,
                  timestamp TEXT)''')
    
    # جدول الإعدادات المحفوظة
    c.execute('''CREATE TABLE IF NOT EXISTS saved_sensitivities
                 (user_id INTEGER,
                  preset_name TEXT,
                  sensitivity_data TEXT,
                  created_at TEXT,
                  PRIMARY KEY (user_id, preset_name))''')
    
    # جدول الإنجازات
    c.execute('''CREATE TABLE IF NOT EXISTS achievements
                 (user_id INTEGER,
                  achievement_name TEXT,
                  unlocked_at TEXT,
                  PRIMARY KEY (user_id, achievement_name))''')
    
    # جدول تحليل الأداء
    c.execute('''CREATE TABLE IF NOT EXISTS performance
                 (user_id INTEGER,
                  date TEXT,
                  games_played INTEGER DEFAULT 0,
                  wins INTEGER DEFAULT 0,
                  kills INTEGER DEFAULT 0,
                  headshots INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, date))''')
    
    conn.commit()
    conn.close()

init_db()

# ========== نظام المستويات والخبرة ==========
LEVELS = {
    1: {"name": "🥉 برونزي", "xp_needed": 0, "reward": "إعدادات أساسية"},
    2: {"name": "🥈 فضي", "xp_needed": 100, "reward": "فتح /save_preset"},
    3: {"name": "🥇 ذهبي", "xp_needed": 250, "reward": "إعدادات احترافية"},
    4: {"name": "💎 بلاتيني", "xp_needed": 500, "reward": "نصائح متقدمة"},
    5: {"name": "🔮 دايموند", "xp_needed": 1000, "reward": "إعدادات الجيروسكوب"},
    6: {"name": "👑 Ace", "xp_needed": 2000, "reward": "إعدادات القناص"},
    7: {"name": "⭐ Conqueror", "xp_needed": 5000, "reward": "جميع الإعدادات المميزة"}
}

ACHIEVEMENTS = {
    "first_command": {"name": "🎯 أول خطوة", "xp": 10, "desc": "استخدم أول أمر"},
    "save_preset": {"name": "💾 حافظ", "xp": 25, "desc": "احفظ أول إعداداتك"},
    "sniper_master": {"name": "🎯 قناص محترف", "xp": 50, "desc": "اطلع على إعدادات القناص 5 مرات"},
    "style_master": {"name": "🖐️ متعدد الأساليب", "xp": 30, "desc": "جرب أسلوب لعب مختلف"},
    "level_5": {"name": "🔮 دايموند", "xp": 100, "desc": "وصل إلى مستوى دايموند"},
    "level_7": {"name": "⭐ كونكرور", "xp": 200, "desc": "وصل إلى أعلى مستوى"},
    "win_10": {"name": "🏆 انتصارات", "xp": 75, "desc": "سجل 10 انتصارات"},
    "kill_50": {"name": "⚔️ قاتل محترف", "xp": 80, "desc": "حققت 50 قتلة"}
}

# ========== الترجمة (دعم لغات متعدد) ==========
TRANSLATIONS = {
    "ar": {
        "welcome": "🎮 مرحباً بك في بوت ببجي!",
        "help": "📖 قائمة الأوامر",
        "sensitivity": "🎯 إعدادات الحساسية",
        "profile": "🏆 ملفك الشخصي",
        "settings": "⚙️ الإعدادات"
    },
    "en": {
        "welcome": "🎮 Welcome to PUBG Bot!",
        "help": "📖 Commands List",
        "sensitivity": "🎯 Sensitivity Settings",
        "profile": "🏆 Your Profile",
        "settings": "⚙️ Settings"
    }
}

# ========== إعدادات القناص ==========
SNIPER_SETTINGS = {
    "awm": {"name": "AWM", "no_gyro": 35, "gyro": 150, "tips": "أقوى قناص، يحتاج ثبات"},
    "m24": {"name": "M24", "no_gyro": 40, "gyro": 160, "tips": "سرعة عالية، مناسب للحركة"},
    "kar98": {"name": "Kar98k", "no_gyro": 45, "gyro": 170, "tips": "كلاسيكي، دقة ممتازة"},
    "mosin": {"name": "Mosin", "no_gyro": 45, "gyro": 170, "tips": "مشابه للكار98"}
}

# ========== أساليب اللعب ==========
PLAY_STYLES = {
    "one_finger": {"name": "🖐️ إصبع واحد", "sens": 110, "gyro": 400, "tips": "استخدم زر نار كبير"},
    "two_fingers": {"name": "✌️ إصبعين", "sens": 95, "gyro": 330, "tips": "الأفضل للمبتدئين"},
    "three_fingers": {"name": "👌 ثلاثة أصابع", "sens": 80, "gyro": 280, "tips": "سرعة استجابة عالية"},
    "four_fingers": {"name": "🖖 أربعة أصابع", "sens": 70, "gyro": 250, "tips": "للمحترفين"},
    "claw": {"name": "🦞 Claw", "sens": 65, "gyro": 220, "tips": "أصعب أسلوب، الأقوى"}
}

# ========== دوال إدارة المستخدمين ==========
def add_xp(user_id, xp_amount):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    
    current_xp, current_level = row
    new_xp = current_xp + xp_amount
    new_level = current_level
    
    while new_level < 7 and new_xp >= LEVELS[new_level + 1]["xp_needed"]:
        new_level += 1
        send_message(user_id, f"🎉 *تهانينا!*\n\nرُقيت إلى {LEVELS[new_level]['name']}\n✨ {LEVELS[new_level]['reward']}")
    
    c.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, user_id))
    conn.commit()
    conn.close()
    return new_level > current_level

def unlock_achievement(user_id, achievement_key):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM achievements WHERE user_id = ? AND achievement_name = ?", (user_id, achievement_key))
    if c.fetchone():
        conn.close()
        return False
    
    achievement = ACHIEVEMENTS[achievement_key]
    c.execute("INSERT INTO achievements (user_id, achievement_name, unlocked_at) VALUES (?, ?, ?)",
              (user_id, achievement_key, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    add_xp(user_id, achievement["xp"])
    send_message(user_id, f"🏆 *إنجاز جديد!*\n\n{achievement['name']}\n{achievement['desc']}\n+{achievement['xp']} XP")
    return True

def save_user(user_id, username, first_name):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_seen, play_style) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().isoformat(), "two_fingers"))
    c.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()
    unlock_achievement(user_id, "first_command")

def save_stats(command, user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO stats (command, user_id, timestamp) VALUES (?, ?, ?)",
              (command, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    add_xp(user_id, 1)

# ========== دوال تحليل الأداء ==========
def update_performance(user_id, games=0, wins=0, kills=0, headshots=0):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO performance (user_id, date) VALUES (?, ?)", (user_id, today))
    c.execute("UPDATE performance SET games_played = games_played + ?, wins = wins + ?, kills = kills + ?, headshots = headshots + ? WHERE user_id = ? AND date = ?",
              (games, wins, kills, headshots, user_id, today))
    conn.commit()
    conn.close()
    
    # التحقق من الإنجازات
    c = conn.cursor()
    c.execute("SELECT SUM(wins) FROM performance WHERE user_id = ?", (user_id,))
    total_wins = c.fetchone()[0] or 0
    c.execute("SELECT SUM(kills) FROM performance WHERE user_id = ?", (user_id,))
    total_kills = c.fetchone()[0] or 0
    conn.close()
    
    if total_wins >= 10:
        unlock_achievement(user_id, "win_10")
    if total_kills >= 50:
        unlock_achievement(user_id, "kill_50")

def get_performance_stats(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    
    # إجمالي الإحصائيات
    c.execute("SELECT SUM(games_played), SUM(wins), SUM(kills), SUM(headshots) FROM performance WHERE user_id = ?", (user_id,))
    total = c.fetchone()
    
    # آخر 7 أيام
    c.execute("SELECT date, games_played, wins, kills FROM performance WHERE user_id = ? ORDER BY date DESC LIMIT 7", (user_id,))
    recent = c.fetchall()
    
    conn.close()
    
    if not total or total[0] is None:
        return "📊 لا توجد بيانات أداء بعد. استخدم /add_stats لإضافة إحصائياتك"
    
    games, wins, kills, headshots = total
    win_rate = (wins / games * 100) if games > 0 else 0
    kd = kills / games if games > 0 else 0
    
    recent_text = "\n".join([f"📅 {d[0][5:]}: {d[1]} مباراة | {d[2]} فوز | {d[3]} قتلة" for d in recent[:5]]) if recent else "لا توجد بيانات حديثة"
    
    return f"""📊 *تحليل أدائك*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 إجمالي المباريات: {games}
🏆 عدد الانتصارات: {wins}
📈 نسبة الفوز: {win_rate:.1f}%
⚔️ إجمالي القتلات: {kills}
🎯 نسبة إصابات الرأس: {(headshots/kills*100) if kills > 0 else 0:.1f}%
💀 K/D Ratio: {kd:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 *آخر نشاط:*
{recent_text}

💡 استخدم /add_stats لإضافة نتائج مباراة جديدة
"""

# ========== دوال الأزرار التفاعلية ==========
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "🎯 حساسية النار"}, {"text": "🔫 إعدادات القناص"}],
            [{"text": "🖐️ أسلوب اللعب"}, {"text": "🏆 ملفي الشخصي"}],
            [{"text": "📊 تحليل الأداء"}, {"text": "⚙️ الإعدادات"}],
            [{"text": "❓ مساعدة"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_sensitivity_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🎯 بدون جيروسكوب", "callback_data": "no_gyro"}],
            [{"text": "📳 مع جيروسكوب", "callback_data": "gyro"}],
            [{"text": "🔫 إعدادات القناص", "callback_data": "sniper"}],
            [{"text": "◀️ رجوع", "callback_data": "back_main"}]
        ]
    }

# ========== دوال الصوت ==========
def send_voice_command(chat_id, command_type):
    """إرسال ردود صوتية نصية (بدلاً من ملفات صوتية حقيقية)"""
    voice_responses = {
        "welcome": "🎤 أهلاً بك في بوت ببجي! يمكنك استخدام الأزرار للتنقل",
        "sensitivity": "🎤 إعدادات الحساسية: ريد دوت 95% بدون جيروسكوب، 330% مع جيروسكوب",
        "victory": "🎤 فوز رائع! أداء ممتاز اليوم",
        "tip": "🎤 نصيحة اليوم: تدرب على التصويب في وضع التدريب"
    }
    return voice_responses.get(command_type, "🎤 أمر غير معروف")

# ========== دوال الإشعارات الصوتية ==========
def send_notification(user_id, message):
    send_message(user_id, f"🔔 {message}")

def periodic_tips():
    """إرسال نصائح دورية"""
    tips = [
        "💡 نصيحة: استخدم الجيروسكوب لتحسين دقتك",
        "🎯 تدرب يومياً في وضع التدريب لمدة 10 دقائق",
        "📊 تتبع إحصائياتك باستخدام /stats",
        "🔫 جرب إعدادات القناص المختلفة مع /sniper"
    ]
    while True:
        time.sleep(86400)  # 24 ساعة
        conn = sqlite3.connect('pubg_bot.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE notification_enabled = 1")
        users = c.fetchall()
        conn.close()
        tip = tips[int(time.time()) % len(tips)]
        for user in users:
            send_notification(user[0], tip)

# ========== دوال التليجرام ==========
def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)
    
    try:
        response = requests.post(URL + "sendMessage", json=payload)
        return response.ok
    except:
        return False

def answer_callback(callback_id, text):
    """الرد على ضغطات الأزرار"""
    payload = {"callback_query_id": callback_id, "text": text, "show_alert": False}
    try:
        requests.post(URL + "answerCallbackQuery", json=payload)
    except:
        pass

# ========== محتوى الرسائل ==========
def get_no_gyro():
    return "🎯 *بدون جيروسكوب*\n\nريد دوت: 95%\n2x: 70%\n3x: 60%\n4x: 50%\n6x: 45%"

def get_gyro():
    return "📳 *مع جيروسكوب*\n\nريد دوت: 330%\n2x: 280%\n3x: 230%\n4x: 180%\n6x: 160%"

def get_sniper_text():
    text = "🔫 *إعدادات القناصات*\n\n"
    for key, s in SNIPER_SETTINGS.items():
        text += f"┌ *{s['name']}*\n├ بدون جيروسكوب: {s['no_gyro']}%\n├ مع جيروسكوب: {s['gyro']}%\n└ {s['tips']}\n\n"
    return text

def get_profile_text(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT xp, level, play_style FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    c.execute("SELECT achievement_name FROM achievements WHERE user_id = ?", (user_id,))
    achievements = [r[0] for r in c.fetchall()]
    conn.close()
    
    if not row:
        return "❌ خطأ في جلب البيانات"
    
    xp, level, play_style = row
    style_name = PLAY_STYLES.get(play_style, PLAY_STYLES["two_fingers"])["name"]
    next_xp = LEVELS[level + 1]["xp_needed"] - xp if level < 7 else 0
    
    achievements_text = "\n".join([f"🏅 {ACHIEVEMENTS[a]['name']}" for a in achievements[:5]]) if achievements else "لا توجد إنجازات"
    
    return f"""🏆 *ملفك الشخصي*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
{LEVELS[level]['name']} *المستوى {level}*
📊 XP: {xp}
✨ {LEVELS[level]['reward']}
{'📈 المتبقي للمستوى التالي: ' + str(next_xp) + ' XP' if level < 7 else '👑 أقصى مستوى!'}

🖐️ أسلوب اللعب: {style_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏅 *الإنجازات:*
{achievements_text}
"""

def get_settings_text(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT theme, notification_enabled, language FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return "❌ خطأ"
    
    theme, notif, lang = row
    return f"""⚙️ *إعداداتك*

🌙 الوضع: {'ليلي' if theme == 'dark' else 'نهاري'}
🔔 الإشعارات: {'مفعّلة' if notif else 'ملغاة'}
🌐 اللغة: {'العربية' if lang == 'ar' else 'English'}

📌 *لتغيير أي إعداد:*
/theme - تغيير الوضع
/notify - تفعيل/إلغاء الإشعارات
/lang - تغيير اللغة
"""

def get_help_text():
    return """📖 *قائمة الأوامر الكاملة*

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *الحساسية:*
/sensitivity_full - جميع الإعدادات
/no_gyro - بدون جيروسكوب
/gyro - مع جيروسكوب
/sniper - إعدادات القناصات

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖐️ *أساليب اللعب:*
/play_style - عرض جميع الأساليب
/set_style {key} - تعيين أسلوبك
/my_style - أسلوبك الحالي

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 *المستخدم:*
/profile - ملفك الشخصي
/stats - إحصائياتك
/leaderboard - الترتيب العام

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *الأداء:*
/performance - تحليل أدائك
/add_stats - إضافة إحصائيات مباراة
/reset_stats - تصفير الإحصائيات

━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ *إعدادات:*
/theme - وضع الليل/النهار
/notify - تفعيل الإشعارات
/lang - تغيير اللغة

━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *نصيحة:* استخدم الأزرار التفاعلية للتنقل السريع!
"""

# ========== معالجة الأزرار ==========
def handle_callback(callback_query):
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    data = callback_query["data"]
    
    responses = {
        "no_gyro": get_no_gyro(),
        "gyro": get_gyro(),
        "sniper": get_sniper_text(),
        "back_main": get_start_message()
    }
    
    if data in responses:
        send_message(chat_id, responses[data], get_main_keyboard())
    else:
        answer_callback(callback_id, "سيتم إضافته قريباً!")
    
    answer_callback(callback_id, "")

# ========== معالجة النصوص ==========
def get_start_message():
    return """🎮 *بوت ببجي المتكامل* 🎮

✨ *المميزات الجديدة:*

🎨 *أزرار تفاعلية* - تنقل سهل
🎤 *أوامر صوتية* - ردود نصية مسموعة
📊 *تحليل أداء* - إحصائيات متقدمة
🔊 *إشعارات صوتية* - تنبيهات ذكية

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 استخدم الأزرار أدناه للتنقل
أو أرسل /help لجميع الأوامر
"""

def handle_message(chat_id, text, username=None, first_name=None):
    save_user(chat_id, username, first_name)
    save_stats(text, chat_id)
    
    # معالجة الأزرار النصية (من لوحة المفاتيح)
    button_commands = {
        "🎯 حساسية النار": lambda: send_message(chat_id, "اختر نوع الحساسية:", get_sensitivity_keyboard()),
        "🔫 إعدادات القناص": lambda: send_message(chat_id, get_sniper_text(), get_main_keyboard()),
        "🖐️ أسلوب اللعب": lambda: send_message(chat_id, get_play_styles_text(), get_main_keyboard()),
        "🏆 ملفي الشخصي": lambda: send_message(chat_id, get_profile_text(chat_id), get_main_keyboard()),
        "📊 تحليل الأداء": lambda: send_message(chat_id, get_performance_stats(chat_id), get_main_keyboard()),
        "⚙️ الإعدادات": lambda: send_message(chat_id, get_settings_text(chat_id), get_main_keyboard()),
        "❓ مساعدة": lambda: send_message(chat_id, get_help_text(), get_main_keyboard())
    }
    
    if text in button_commands:
        button_commands[text]()
        return
    
    # معالجة الأوامر النصية
    if text.startswith('/'):
        cmd = text.split()[0].lower()
        
        commands = {
            "/start": lambda: send_message(chat_id, get_start_message(), get_main_keyboard()),
            "/help": lambda: send_message(chat_id, get_help_text(), get_main_keyboard()),
            "/sensitivity_full": lambda: send_message(chat_id, get_no_gyro() + "\n\n" + get_gyro(), get_main_keyboard()),
            "/no_gyro": lambda: send_message(chat_id, get_no_gyro(), get_main_keyboard()),
            "/gyro": lambda: send_message(chat_id, get_gyro(), get_main_keyboard()),
            "/sniper": lambda: send_message(chat_id, get_sniper_text(), get_main_keyboard()),
            "/profile": lambda: send_message(chat_id, get_profile_text(chat_id), get_main_keyboard()),
            "/performance": lambda: send_message(chat_id, get_performance_stats(chat_id), get_main_keyboard()),
            "/voice": lambda: send_message(chat_id, send_voice_command(chat_id, "welcome")),
            "/stats": lambda: send_message(chat_id, get_stats_text(chat_id), get_main_keyboard()),
            "/leaderboard": lambda: send_message(chat_id, get_leaderboard_text(), get_main_keyboard()),
            "/theme": lambda: handle_theme(chat_id),
            "/notify": lambda: handle_notify(chat_id),
            "/lang": lambda: handle_lang(chat_id),
            "/my_style": lambda: send_message(chat_id, get_my_style_text(chat_id), get_main_keyboard())
        }
        
        if cmd in commands:
            commands[cmd]()
        elif cmd == "/add_stats" and len(text.split()) >= 4:
            handle_add_stats(chat_id, text)
        elif cmd == "/set_style" and len(text.split()) > 1:
            handle_set_style(chat_id, text.split()[1])
        elif cmd == "/play_style":
            send_message(chat_id, get_play_styles_text(), get_main_keyboard())
        else:
            send_message(chat_id, "❓ أمر غير معروف. أرسل /help", get_main_keyboard())
    else:
        send_message(chat_id, "📌 أرسل /help لبدء الاستخدام أو استخدم الأزرار", get_main_keyboard())

def get_play_styles_text():
    text = "🎮 *أساليب اللعب المتاحة*\n\n"
    for key, style in PLAY_STYLES.items():
        text += f"┌ {style['name']}\n├ حساسية: {style['sens']}%\n├ جيروسكوب: {style['gyro']}%\n└ {style['tips']}\n\n"
    text += "📌 استخدم `/set_style {key}` لتعيين أسلوبك\nمثال: `/set_style four_fingers`"
    return text

def get_my_style_text(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT play_style FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        style = PLAY_STYLES.get(row[0], PLAY_STYLES["two_fingers"])
        return f"🖐️ *أسلوبك الحالي:* {style['name']}\n\n{style['tips']}"
    return "❌ لم يتم العثور على أسلوبك"

def handle_set_style(user_id, style_key):
    if style_key in PLAY_STYLES:
        conn = sqlite3.connect('pubg_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET play_style = ? WHERE user_id = ?", (style_key, user_id))
        conn.commit()
        conn.close()
        unlock_achievement(user_id, "style_master")
        send_message(user_id, f"✅ تم تعيين أسلوب اللعب إلى {PLAY_STYLES[style_key]['name']}", get_main_keyboard())
    else:
        send_message(user_id, f"❌ أسلوب غير موجود. المتاح: {', '.join(PLAY_STYLES.keys())}")

def handle_add_stats(user_id, text):
    parts = text.split()
    if len(parts) >= 4:
        try:
            games = int(parts[1])
            wins = int(parts[2])
            kills = int(parts[3])
            headshots = int(parts[4]) if len(parts) > 4 else 0
            update_performance(user_id, games, wins, kills, headshots)
            send_message(user_id, f"✅ تم تحديث الإحصائيات!\n🎮 {games} مباراة | 🏆 {wins} فوز | ⚔️ {kills} قتلة", get_main_keyboard())
        except:
            send_message(user_id, "❌ خطأ: تأكد من إدخال أرقام صحيحة")
    else:
        send_message(user_id, "❌ استخدم: `/add_stats {مباريات} {انتصارات} {قتلات} {إصابات_رأس}`\nمثال: `/add_stats 10 3 25 8`")

def get_stats_text(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM stats WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    conn.close()
    return f"📊 *إحصائياتك*\n\n📝 عدد الأوامر: {total}\n💡 استخدم /performance لتحليل أدائك في اللعب"

def get_leaderboard_text():
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, xp, level FROM users ORDER BY xp DESC LIMIT 10")
    top = c.fetchall()
    conn.close()
    
    text = "🏆 *ترتيب اللاعبين* 🏆\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, name, xp, level) in enumerate(top):
        medal = medals[i] if i < 3 else f"{i+1}."
        display_name = name or f"مستخدم{uid}"
        text += f"{medal} {display_name[:15]} - {LEVELS[level]['name']} ({xp} XP)\n"
    return text

def handle_theme(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT theme FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    new_theme = "dark" if row and row[0] == "light" else "light"
    c.execute("UPDATE users SET theme = ? WHERE user_id = ?", (new_theme, user_id))
    conn.commit()
    conn.close()
    send_message(user_id, f"{'🌙' if new_theme == 'dark' else '☀️'} تم التبديل إلى وضع {'الليل' if new_theme == 'dark' else 'النهار'}")

def handle_notify(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT notification_enabled FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    new_status = 0 if row and row[0] == 1 else 1
    c.execute("UPDATE users SET notification_enabled = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    send_message(user_id, f"🔔 الإشعارات {'مفعّلة' if new_status else 'ملغاة'}")

def handle_lang(user_id):
    conn = sqlite3.connect('pubg_bot.db')
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    new_lang = "en" if row and row[0] == "ar" else "ar"
    c.execute("UPDATE users SET language = ? WHERE user_id = ?", (new_lang, user_id))
    conn.commit()
    conn.close()
    send_message(user_id, f"🌐 اللغة changed to {'English' if new_lang == 'en' else 'العربية'}")

# ========== Flask Webhook ==========
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json()
    if update:
        if "callback_query" in update:
            handle_callback(update["callback_query"])
        elif "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            username = msg["chat"].get("username")
            first_name = msg["chat"].get("first_name")
            threading.Thread(target=handle_message, args=(chat_id, text, username, first_name)).start()
    return "ok", 200

@app.route("/")
def home():
    return "✅ بوت ببجي المتكامل - جميع الميزات مفعلة!", 200

# ========== التشغيل ==========
if __name__ == "__main__":
    print("🚀 تشغيل بوت ببجي المتكامل...")
    print("✅ الميزات الجديدة المفعلة:")
    print("   🎨 أزرار تفاعلية (Inline Keyboard)")
    print("   🎤 أوامر صوتية نصية")
    print("   📊 تحليل أداء متقدم")
    print("   🔊 إشعارات ذكية")
    
    # تشغيل الإشعارات الدورية
    threading.Thread(target=periodic_tips, daemon=True).start()
    
    app.run(host="0.0.0.0", port=5000)
