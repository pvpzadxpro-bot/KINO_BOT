import telebot
from telebot import types
import json
import os
import threading
import time
import requests
from flask import Flask

# ======================== CONFIG ========================
BOT_TOKEN  = "8772023380:AAFLPN8GPBVs8pyRZ10I3maz9IYRl2DI8fc"
ADMIN_ID   = 7424107874           # ID-и худатро бигзор
CHANNELS   = ["@zadxproooo", "@zadxprootziv"]
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT   = 5000
# ========================================================

bot     = telebot.TeleBot(BOT_TOKEN)
app     = Flask(__name__)
DB_FILE = "movies.json"

# паёми охирини бот барои ҳар юзер
last_msg: dict = {}

# вазъи FSM барои админ
admin_state: dict = {}


# ======================== DATABASE ========================

def load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_db(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ======================== CLEAN SEND ========================

def delete_last(chat_id: int):
    """Паёми охирини ботро нест мекунад."""
    mid = last_msg.get(chat_id)
    if mid:
        try:
            bot.delete_message(chat_id, mid)
        except Exception:
            pass
        last_msg.pop(chat_id, None)


def send_clean(chat_id: int, text: str, **kwargs):
    """Паёми кӯҳнаро нест, паёми нав мефиристад."""
    delete_last(chat_id)
    msg = bot.send_message(chat_id, text, **kwargs)
    last_msg[chat_id] = msg.message_id
    return msg


# ======================== SUB CHECK ========================

def is_subscribed(user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            m = bot.get_chat_member(ch, user_id)
            if m.status in ("left", "kicked", "banned"):
                return False
        except Exception:
            return False
    return True


def sub_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in CHANNELS:
        kb.add(types.InlineKeyboardButton(
            f"📢 Обуна шудан ба {ch}",
            url=f"https://t.me/{ch.lstrip('@')}"
        ))
    kb.add(types.InlineKeyboardButton("✅ Санҷиш кардан", callback_data="check_sub"))
    return kb


def require_sub(message: telebot.types.Message) -> bool:
    if is_subscribed(message.from_user.id):
        return True
    send_clean(
        message.chat.id,
        "📢 *Барои истифода аз бот*\nлутфан аввал ба каналҳо обуна шав:",
        parse_mode="Markdown",
        reply_markup=sub_keyboard()
    )
    return False


# ======================== KEYBOARDS ========================

def main_keyboard(user_id: int) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎬 Кино гирифтан")
    if user_id == ADMIN_ID:
        kb.add("➕ Илова кардан", "📋 Рӯйхат")
        kb.add("🗑 Нест кардан")
    return kb


# ======================== KEEP-ALIVE ========================

@app.route("/")
def home():
    return "✅ Bot is alive!"


def keep_alive_loop():
    time.sleep(30)
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            print("🔁 Keep-alive ping sent")
        except Exception as e:
            print(f"⚠️ Keep-alive error: {e}")
        time.sleep(60)


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


# ======================== HANDLERS ========================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    if not require_sub(message):
        return
    send_clean(
        message.chat.id,
        "🎬 *Movie Bot*\n\nID-и киноро бифирист ё тугмаро пахш кун!",
        parse_mode="Markdown",
        reply_markup=main_keyboard(message.from_user.id)
    )


@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(call: types.CallbackQuery):
    uid = call.from_user.id
    cid = call.message.chat.id

    if is_subscribed(uid):
        try:
            bot.delete_message(cid, call.message.message_id)
        except Exception:
            pass
        last_msg.pop(cid, None)
        m = bot.send_message(
            cid,
            "✅ *Ташаккур!* Акнун метавонӣ ботро истифода барӣ 🎬",
            parse_mode="Markdown",
            reply_markup=main_keyboard(uid)
        )
        last_msg[cid] = m.message_id
    else:
        bot.answer_callback_query(call.id, "❌ Ҳанӯз обуна нашудаӣ!", show_alert=True)


@bot.message_handler(func=lambda m: m.text == "🎬 Кино гирифтан")
def btn_get_movie(message):
    if not require_sub(message):
        return
    send_clean(message.chat.id, "🔢 ID-и киноро бифирист (масалан: 1, 2, 3...)")


@bot.message_handler(func=lambda m: m.text == "📋 Рӯйхат" and m.from_user.id == ADMIN_ID)
def btn_list(message):
    db = load_db()
    if not db:
        send_clean(message.chat.id, "❌ Кино вуҷуд надорад!")
        return
    text = "📋 *Рӯйхати кино:*\n\n"
    for mid, info in db.items():
        text += f"🎬 ID: `{mid}` — {info['name']}\n"
    send_clean(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "➕ Илова кардан" and m.from_user.id == ADMIN_ID)
def btn_add(message):
    admin_state[message.from_user.id] = {"step": "wait_name"}
    send_clean(message.chat.id, "✏️ Номи киноро бифирист:")


@bot.message_handler(func=lambda m: m.text == "🗑 Нест кардан" and m.from_user.id == ADMIN_ID)
def btn_delete(message):
    admin_state[message.from_user.id] = {"step": "wait_del_id"}
    send_clean(message.chat.id, "🔢 ID-и киноеро ки мехоҳӣ нест кунӣ бифирист:")


@bot.message_handler(content_types=["text", "video", "document", "photo"])
def handle_all(message):
    uid = message.from_user.id
    cid = message.chat.id
    db  = load_db()

    # ── ADMIN FSM ──
    if uid == ADMIN_ID and uid in admin_state:
        step = admin_state[uid]["step"]

        if step == "wait_name":
            admin_state[uid] = {"step": "wait_file", "data": {"name": message.text.strip()}}
            send_clean(cid, "📤 Акнун файли кино/видеоро бифирист:")
            return

        elif step == "wait_file":
            if message.video:
                fid, ftype = message.video.file_id, "video"
            elif message.document:
                fid, ftype = message.document.file_id, "document"
            elif message.photo:
                fid, ftype = message.photo[-1].file_id, "photo"
            else:
                send_clean(cid, "❌ Лутфан файл/видео бифирист!")
                return
            admin_state[uid]["data"].update({"file_id": fid, "file_type": ftype})
            admin_state[uid]["step"] = "wait_id"
            send_clean(cid, "🔢 ID барои ин кино бигзор (масалан: 1, 2, 100...):")
            return

        elif step == "wait_id":
            movie_id = message.text.strip()
            if movie_id in db:
                send_clean(cid, f"⚠️ ID `{movie_id}` аллакай вуҷуд дорад! ID-и дигар бигзор:", parse_mode="Markdown")
                return
            d = admin_state[uid]["data"]
            db[movie_id] = {"name": d["name"], "file_id": d["file_id"], "file_type": d["file_type"]}
            save_db(db)
            del admin_state[uid]
            send_clean(cid, f"✅ *{d['name']}* илова шуд!\n🔢 ID: `{movie_id}`", parse_mode="Markdown")
            return

        elif step == "wait_del_id":
            movie_id = message.text.strip()
            if movie_id not in db:
                send_clean(cid, f"❌ ID `{movie_id}` ёфт нашуд!", parse_mode="Markdown")
            else:
                name = db[movie_id]["name"]
                del db[movie_id]
                save_db(db)
                send_clean(cid, f"🗑 *{name}* нест шуд!", parse_mode="Markdown")
            del admin_state[uid]
            return

    # ── ЮЗЕР: ID ──
    if message.text:
        movie_id = message.text.strip()
        if movie_id in db:
            if not require_sub(message):
                return
            movie   = db[movie_id]
            caption = f"🎬 *{movie['name']}*\n🔢 ID: `{movie_id}`"
            delete_last(cid)
            if movie["file_type"] == "video":
                m = bot.send_video(cid, movie["file_id"], caption=caption, parse_mode="Markdown")
            elif movie["file_type"] == "document":
                m = bot.send_document(cid, movie["file_id"], caption=caption, parse_mode="Markdown")
            else:
                m = bot.send_photo(cid, movie["file_id"], caption=caption, parse_mode="Markdown")
            last_msg[cid] = m.message_id
        else:
            send_clean(cid, f"❌ Кино бо ID `{movie_id}` ёфт нашуд!", parse_mode="Markdown")


# ======================== MAIN ========================

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive_loop, daemon=True).start()
    print("✅ Bot started...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)