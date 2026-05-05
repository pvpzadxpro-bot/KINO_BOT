import telebot
from telebot import types
import json
import os
import time
import threading
import requests
from flask import Flask

# ======================== CONFIG ========================
BOT_TOKEN    = "8772023380:AAGUCYu1qTwHHyz-XkerjtHc4mP_DpEhWn8"
ADMIN_ID     = 7424107874
CHANNELS     = ["@zadxproooo", "@zadxpro_film"]
DB_FILE      = "movies.json"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
# ========================================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

last_msg: dict    = {}
admin_state: dict = {}


# ======================== FLASK (KEEP-ALIVE) ========================

@app.route("/")
def home():
    return "✅ Bot is running!", 200

@app.route("/health")
def health():
    return {"status": "ok", "bot": "zadxpro"}, 200

def run_flask():
    """Flask серверро дар port 10000 иҷро мекунад (Render талаб мекунад)."""
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    """
    Ҳар 1 дақиқа ба худ HTTP сӯрохӣ мефиристад,
    то Render бот ро хоб накунад.
    """
    while True:
        time.sleep(60)  # 60 сония = 1 дақиқа
        try:
            r = requests.get(RENDER_URL + "/health", timeout=10)
            print(f"[KeepAlive] ✅ Ping OK — status: {r.status_code}")
        except Exception as e:
            print(f"[KeepAlive] ⚠️ Ping failed: {e}")


# ======================== DATABASE ========================

def load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_db(data: dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ======================== CLEAN SEND ========================

def delete_last(chat_id: int):
    mid = last_msg.get(chat_id)
    if mid:
        try:
            bot.delete_message(chat_id, mid)
        except Exception:
            pass
        last_msg.pop(chat_id, None)


def send_clean(chat_id: int, text: str, **kwargs):
    delete_last(chat_id)
    msg = bot.send_message(chat_id, text, **kwargs)
    last_msg[chat_id] = msg.message_id
    return msg


# ======================== SUB CHECK ========================

def get_unsubscribed(user_id: int) -> list:
    result = []
    for ch in CHANNELS:
        try:
            m = bot.get_chat_member(ch, user_id)
            if m.status in ("left", "kicked", "banned"):
                result.append(ch)
        except Exception:
            result.append(ch)
    return result


def is_subscribed(user_id: int) -> bool:
    return len(get_unsubscribed(user_id)) == 0


def sub_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in get_unsubscribed(user_id):
        kb.add(types.InlineKeyboardButton(
            "➕ Обуна шудан — " + ch,
            url="https://t.me/" + ch.lstrip("@")
        ))
    kb.add(types.InlineKeyboardButton("✅ Санҷиш кардан", callback_data="check_sub"))
    return kb


def sub_text(user_id: int) -> str:
    unsub = get_unsubscribed(user_id)
    ch_list = "\n".join(["• " + ch for ch in unsub])
    return "📢 Барои истифода аз бот\nба каналҳои зерин обуна шав:\n\n" + ch_list


# ======================== KEYBOARDS ========================

def main_menu_kb(user_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🎬 Кино гирифтан", callback_data="get_movie"))
    kb.add(types.InlineKeyboardButton("📺 Канали кино", url="https://t.me/zadxpro_film"))
    if user_id == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("➕ Илова кардан", callback_data="admin_add"))
        kb.add(types.InlineKeyboardButton("🗑 Нест кардан",  callback_data="admin_del"))
        kb.add(types.InlineKeyboardButton("📋 Рӯйхат",       callback_data="admin_list"))
    return kb


def back_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Бозгашт", callback_data="back_main"))
    return kb


# ======================== HANDLERS ========================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.from_user.id
    cid = message.chat.id
    admin_state.pop(uid, None)

    try:
        bot.delete_message(cid, message.message_id)
    except Exception:
        pass

    if not is_subscribed(uid):
        send_clean(cid, sub_text(uid), reply_markup=sub_keyboard(uid))
        return

    send_clean(
        cid,
        "👋 Хуш омадед!\n\nID-и киноро бифиристед ё тугмаро пахш кунед:",
        reply_markup=main_menu_kb(uid)
    )


# ── Callback: обуна санҷиш ──
@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(call: types.CallbackQuery):
    uid = call.from_user.id
    cid = call.message.chat.id
    mid = call.message.message_id
    unsub = get_unsubscribed(uid)

    if not unsub:
        try:
            bot.edit_message_text(
                "👋 Хуш омадед!\n\nID-и киноро бифиристед ё тугмаро пахш кунед:",
                cid, mid,
                reply_markup=main_menu_kb(uid)
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "✅ Ташаккур! Хуш омадед!")
    else:
        ch_list = "\n".join(["• " + ch for ch in unsub])
        try:
            bot.edit_message_text(
                "📢 Барои истифода аз бот\nба каналҳои зерин обуна шав:\n\n" + ch_list,
                cid, mid,
                reply_markup=sub_keyboard(uid)
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "❌ Ҳанӯз обуна нашудаед!", show_alert=True)


# ── Callback: бозгашт ──
@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(call: types.CallbackQuery):
    uid = call.from_user.id
    cid = call.message.chat.id
    admin_state.pop(uid, None)
    try:
        bot.edit_message_text(
            "👋 Хуш омадед!\n\nID-и киноро бифиристед ё тугмаро пахш кунед:",
            cid, call.message.message_id,
            reply_markup=main_menu_kb(uid)
        )
    except Exception:
        send_clean(
            cid,
            "👋 Хуш омадед!\n\nID-и киноро бифиристед ё тугмаро пахш кунед:",
            reply_markup=main_menu_kb(uid)
        )
    bot.answer_callback_query(call.id)


# ── Callback: кино гирифтан ──
@bot.callback_query_handler(func=lambda c: c.data == "get_movie")
def cb_get_movie(call: types.CallbackQuery):
    uid = call.from_user.id
    cid = call.message.chat.id
    if not is_subscribed(uid):
        ch_list = "\n".join(["• " + ch for ch in get_unsubscribed(uid)])
        try:
            bot.edit_message_text(
                "📢 Барои истифода аз бот\nба каналҳои зерин обуна шав:\n\n" + ch_list,
                cid, call.message.message_id,
                reply_markup=sub_keyboard(uid)
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return
    admin_state[uid] = {"step": "user_wait_id"}
    try:
        bot.edit_message_text(
            "🔢 ID-и киноро бифиристед:\n(масалан: 1, 2, 100...)",
            cid, call.message.message_id,
            reply_markup=back_kb()
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id)


# ── Callback: Admin — илова ──
@bot.callback_query_handler(func=lambda c: c.data == "admin_add")
def cb_admin_add(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Иҷозат надоред!")
        return
    uid = call.from_user.id
    cid = call.message.chat.id
    admin_state[uid] = {"step": "wait_name"}
    try:
        bot.edit_message_text(
            "✏️ Номи киноро бифиристед:",
            cid, call.message.message_id,
            reply_markup=back_kb()
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id)


# ── Callback: Admin — нест ──
@bot.callback_query_handler(func=lambda c: c.data == "admin_del")
def cb_admin_del(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Иҷозат надоред!")
        return
    uid = call.from_user.id
    cid = call.message.chat.id
    admin_state[uid] = {"step": "wait_del_id"}
    try:
        bot.edit_message_text(
            "🔢 ID-и киноеро, ки мехоҳед нест кунед, бифиристед:",
            cid, call.message.message_id,
            reply_markup=back_kb()
        )
    except Exception:
        pass
    bot.answer_callback_query(call.id)


# ── Callback: Admin — рӯйхат ──
@bot.callback_query_handler(func=lambda c: c.data == "admin_list")
def cb_admin_list(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Иҷозат надоред!")
        return
    cid = call.message.chat.id
    db = load_db()
    if not db:
        text = "❌ Кино вуҷуд надорад!"
    else:
        lines = ["📋 Рӯйхати кино:\n"]
        for mid, info in db.items():
            lines.append("🎬 ID: " + mid + " — " + info.get("name", "Номаълум"))
        text = "\n".join(lines)

    if len(text) > 4096:
        text = text[:4090] + "\n..."

    try:
        bot.edit_message_text(text, cid, call.message.message_id, reply_markup=back_kb())
    except Exception:
        send_clean(cid, text, reply_markup=back_kb())
    bot.answer_callback_query(call.id)


# ── Матн ва файлҳо: FSM ──
@bot.message_handler(content_types=["text", "video", "document", "photo"])
def handle_all(message):
    uid = message.from_user.id
    cid = message.chat.id
    db  = load_db()

    state = admin_state.get(uid, {})
    step  = state.get("step")

    if not step:
        if message.text and not message.text.startswith("/"):
            movie_id = message.text.strip()
            try:
                bot.delete_message(cid, message.message_id)
            except Exception:
                pass
            if not is_subscribed(uid):
                send_clean(cid, sub_text(uid), reply_markup=sub_keyboard(uid))
                return
            if movie_id in db:
                _send_movie(cid, uid, movie_id, db[movie_id])
            else:
                send_clean(cid, "❌ Кино бо ID " + movie_id + " ёфт нашуд!", reply_markup=back_kb())
        return

    # ── Юзер: интизори ID ──
    if step == "user_wait_id":
        if not message.text:
            send_clean(cid, "❌ Лутфан ID-ро ба сифати рақам бифиристед!", reply_markup=back_kb())
            return
        movie_id = message.text.strip()
        try:
            bot.delete_message(cid, message.message_id)
        except Exception:
            pass
        if not is_subscribed(uid):
            send_clean(cid, sub_text(uid), reply_markup=sub_keyboard(uid))
            return
        if movie_id in db:
            admin_state.pop(uid, None)
            _send_movie(cid, uid, movie_id, db[movie_id])
        else:
            send_clean(cid, "❌ Кино бо ID " + movie_id + " ёфт нашуд!", reply_markup=back_kb())
        return

    # ── Admin FSM ──
    if uid != ADMIN_ID:
        return

    if step == "wait_name":
        if not message.text:
            send_clean(cid, "❌ Лутфан номи киноро матн фиристед!", reply_markup=back_kb())
            return
        admin_state[uid] = {"step": "wait_file", "data": {"name": message.text.strip()}}
        try:
            bot.delete_message(cid, message.message_id)
        except Exception:
            pass
        send_clean(cid, "📤 Акнун файли кино/видеоро бифиристед:", reply_markup=back_kb())
        return

    elif step == "wait_file":
        if message.video:
            fid, ftype = message.video.file_id, "video"
        elif message.document:
            fid, ftype = message.document.file_id, "document"
        elif message.photo:
            fid, ftype = message.photo[-1].file_id, "photo"
        else:
            send_clean(cid, "❌ Лутфан файл ё видео бифиристед!", reply_markup=back_kb())
            return
        try:
            bot.delete_message(cid, message.message_id)
        except Exception:
            pass
        admin_state[uid]["data"].update({"file_id": fid, "file_type": ftype})
        admin_state[uid]["step"] = "wait_id"
        send_clean(cid, "🔢 ID барои ин кино бигзоред:\n(масалан: 1, 2, 100...)", reply_markup=back_kb())
        return

    elif step == "wait_id":
        if not message.text:
            send_clean(cid, "❌ Лутфан ID-ро рақам фиристед!", reply_markup=back_kb())
            return
        movie_id = message.text.strip()
        try:
            bot.delete_message(cid, message.message_id)
        except Exception:
            pass
        if movie_id in db:
            send_clean(cid, "⚠️ ID " + movie_id + " аллакай вуҷуд дорад! ID-и дигар бигзоред:", reply_markup=back_kb())
            return
        d = admin_state[uid]["data"]
        db[movie_id] = {"name": d["name"], "file_id": d["file_id"], "file_type": d["file_type"]}
        save_db(db)
        admin_state.pop(uid, None)
        send_clean(cid, "✅ « " + d["name"] + " » илова шуд!\n🔢 ID: " + movie_id, reply_markup=main_menu_kb(uid))
        return

    elif step == "wait_del_id":
        if not message.text:
            send_clean(cid, "❌ Лутфан ID-ро рақам фиристед!", reply_markup=back_kb())
            return
        movie_id = message.text.strip()
        try:
            bot.delete_message(cid, message.message_id)
        except Exception:
            pass
        if movie_id not in db:
            send_clean(cid, "❌ ID " + movie_id + " ёфт нашуд!", reply_markup=back_kb())
        else:
            name = db[movie_id]["name"]
            del db[movie_id]
            save_db(db)
            admin_state.pop(uid, None)
            send_clean(cid, "🗑 « " + name + " » нест шуд!", reply_markup=main_menu_kb(uid))
        return


def _send_movie(cid: int, uid: int, movie_id: str, movie: dict):
    """Кино фиристодан бо caption ва тугмаи бозгашт."""
    caption = "🎬 " + movie.get("name", "Номаълум") + "\n🆔 ID: " + movie_id
    delete_last(cid)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Бозгашт", callback_data="back_main"))
    try:
        ftype = movie.get("file_type", "video")
        fid   = movie["file_id"]
        if ftype == "video":
            m = bot.send_video(cid, fid, caption=caption, reply_markup=kb)
        elif ftype == "document":
            m = bot.send_document(cid, fid, caption=caption, reply_markup=kb)
        else:
            m = bot.send_photo(cid, fid, caption=caption, reply_markup=kb)
        last_msg[cid] = m.message_id
    except Exception as e:
        send_clean(cid, "❌ Хато ҳангоми фиристодани кино: " + str(e), reply_markup=back_kb())


# ======================== MAIN ========================

if __name__ == "__main__":
    print("✅ Bot started...")
    print(f"🌐 RENDER_URL: {RENDER_URL}")

    # 1) Flask thread — Render порт мекушояд
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask server started.")

    # 2) Keep-alive thread — ҳар 1 дақиқа ping мезанад
    ka_thread = threading.Thread(target=keep_alive, daemon=True)
    ka_thread.start()
    print("⏰ Keep-alive thread started (every 60s).")

    # 3) Bot polling
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            print("⚠️ Хато:", e)
            time.sleep(5)
