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
ADMIN_ID   = 7424107874
CHANNELS   = ["@zadxproooo", "@zadxpro_film"]
DB_FILE    = "movies.json"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT       = int(os.environ.get("PORT", 5000))
# ========================================================

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


# ======================== FLASK (fake port) ========================

@app.route("/")
def home():
    return "✅ Bot is alive!"


def run_flask():
    app.run(host="0.0.0.0", port=PORT)


# ======================== KEEP-ALIVE (30 сония) ========================

def keep_alive_loop():
    time.sleep(30)
    while True:
        try:
            if RENDER_URL:
                requests.get(RENDER_URL, timeout=10)
                print("🔁 Keep-alive ping sent")
        except Exception as e:
            print(f"⚠️ Keep-alive error: {e}")
        time.sleep(30)

last_msg: dict    = {}
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


# ======================== AUTO DELETE ========================

def auto_delete_and_menu(chat_id: int, msg_id: int, user_id: int, delay: int = 10):
    """Паёми киноро баъд аз delay сония удалит карда менюи асосиро мефиристад."""
    def _run():
        time.sleep(delay)
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
        if last_msg.get(chat_id) == msg_id:
            last_msg.pop(chat_id, None)
        try:
            m = bot.send_message(
                chat_id,
                "👋 *Хуш омадед!*\n\nID-и киноро бифирист ё тугмаро пахш кун:",
                parse_mode="Markdown",
                reply_markup=main_menu_kb(user_id)
            )
            last_msg[chat_id] = m.message_id
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


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


# ======================== KEYBOARDS ========================

def main_menu_kb(user_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔍 Поиск бо айди", callback_data="get_movie"))
    kb.add(types.InlineKeyboardButton("📺 Канали кинохо", url="https://t.me/zadxpro_film"))
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

    if not is_subscribed(uid):
        send_clean(
            cid,
            "📢 *Барои истифода аз бот*\nлутфан аввал ба каналҳо обуна шав:",
            parse_mode="Markdown",
            reply_markup=sub_keyboard()
        )
        return

    send_clean(
        cid,
        "👋 *Хуш омадед!*\n\nID-и киноро бифирист ё тугмаро пахш кун:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(uid)
    )


# ── Callback: обуна санҷиш ──
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
            reply_markup=main_menu_kb(uid)
        )
        last_msg[cid] = m.message_id
    else:
        bot.answer_callback_query(call.id, "❌ Ҳанӯз обуна нашудаӣ!", show_alert=True)


# ── Callback: бозгашт ──
@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back_main(call: types.CallbackQuery):
    uid = call.from_user.id
    cid = call.message.chat.id
    admin_state.pop(uid, None)
    try:
        bot.edit_message_text(
            "👋 *Хуш омадед!*\n\nID-и киноро бифирист ё тугмаро пахш кун:",
            cid, call.message.message_id,
            parse_mode="Markdown",
            reply_markup=main_menu_kb(uid)
        )
    except Exception:
        send_clean(
            cid,
            "👋 *Хуш омадед!*\n\nID-и киноро бифирист ё тугмаро пахш кун:",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(uid)
        )


# ── Callback: кино гирифтан ──
@bot.callback_query_handler(func=lambda c: c.data == "get_movie")
def cb_get_movie(call: types.CallbackQuery):
    uid = call.from_user.id
    cid = call.message.chat.id
    if not is_subscribed(uid):
        bot.answer_callback_query(call.id, "❌ Аввал ба каналҳо обуна шав!", show_alert=True)
        return
    admin_state[uid] = {"step": "user_wait_id"}
    try:
        bot.edit_message_text(
            "🔢 *ID-и киноро бифирист:*\n_(масалан: 1, 2, 100...)_",
            cid, call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception:
        pass


# ── Callback: Admin — илова ──
@bot.callback_query_handler(func=lambda c: c.data == "admin_add")
def cb_admin_add(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    uid = call.from_user.id
    cid = call.message.chat.id
    admin_state[uid] = {"step": "wait_name"}
    try:
        bot.edit_message_text(
            "✏️ *Номи киноро бифирист:*",
            cid, call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception:
        pass


# ── Callback: Admin — нест ──
@bot.callback_query_handler(func=lambda c: c.data == "admin_del")
def cb_admin_del(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    uid = call.from_user.id
    cid = call.message.chat.id
    admin_state[uid] = {"step": "wait_del_id"}
    try:
        bot.edit_message_text(
            "🔢 *ID-и киноеро ки мехоҳӣ нест кунӣ бифирист:*",
            cid, call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception:
        pass


# ── Callback: Admin — рӯйхат ──
@bot.callback_query_handler(func=lambda c: c.data == "admin_list")
def cb_admin_list(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    cid = call.message.chat.id
    db = load_db()
    if not db:
        text = "❌ Кино вуҷуд надорад!"
    else:
        text = "📋 *Рӯйхати кино:*\n\n"
        for mid, info in db.items():
            text += f"🎬 ID: `{mid}` — {info['name']}\n"
    try:
        bot.edit_message_text(
            text,
            cid, call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_kb()
        )
    except Exception:
        pass


# ── Матн ва файлҳо: FSM ──
@bot.message_handler(content_types=["text", "video", "document", "photo"])
def handle_all(message):
    uid = message.from_user.id
    cid = message.chat.id
    db  = load_db()

    state = admin_state.get(uid, {})
    step  = state.get("step")

    # ── Юзер: интизори ID ──
    if step == "user_wait_id":
        if not message.text:
            return
        movie_id = message.text.strip()
        try:
            bot.delete_message(cid, message.message_id)
        except Exception:
            pass
        if movie_id in db:
            if not is_subscribed(uid):
                send_clean(
                    cid,
                    "📢 *Барои истифода аз бот*\nлутфан аввал ба каналҳо обуна шав:",
                    parse_mode="Markdown",
                    reply_markup=sub_keyboard()
                )
                return
            movie   = db[movie_id]
            caption = (
                f"🎬 *{movie['name']}*\n"
                f"🎞 Қисм: 1 / 1\n"
                f"🆔 ID: `{movie_id}`"
            )
            delete_last(cid)
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔙 Бозгашт", callback_data="back_main"))
            if movie["file_type"] == "video":
                m = bot.send_video(cid, movie["file_id"], caption=caption,
                                   parse_mode="Markdown", reply_markup=kb)
            elif movie["file_type"] == "document":
                m = bot.send_document(cid, movie["file_id"], caption=caption,
                                      parse_mode="Markdown", reply_markup=kb)
            else:
                m = bot.send_photo(cid, movie["file_id"], caption=caption,
                                   parse_mode="Markdown", reply_markup=kb)
            last_msg[cid] = m.message_id
            admin_state.pop(uid, None)
        else:
            send_clean(
                cid,
                f"❌ Кино бо ID `{movie_id}` ёфт нашуд!",
                parse_mode="Markdown",
                reply_markup=back_kb()
            )
        return

    # ── Admin FSM ──
    if uid == ADMIN_ID and step:

        if step == "wait_name":
            if not message.text:
                return
            admin_state[uid] = {"step": "wait_file", "data": {"name": message.text.strip()}}
            try:
                bot.delete_message(cid, message.message_id)
            except Exception:
                pass
            send_clean(cid, "📤 *Акнун файли кино/видеоро бифирист:*",
                       parse_mode="Markdown", reply_markup=back_kb())
            return

        elif step == "wait_file":
            if message.video:
                fid, ftype = message.video.file_id, "video"
            elif message.document:
                fid, ftype = message.document.file_id, "document"
            elif message.photo:
                fid, ftype = message.photo[-1].file_id, "photo"
            else:
                send_clean(cid, "❌ Лутфан файл/видео бифирист!", reply_markup=back_kb())
                return
            # файл аз чат удалит мешавад, аммо file_id сохранит шуд
            try:
                bot.delete_message(cid, message.message_id)
            except Exception:
                pass
            admin_state[uid]["data"].update({"file_id": fid, "file_type": ftype})
            admin_state[uid]["step"] = "wait_id"
            send_clean(cid, "🔢 *ID барои ин кино бигзор:*\n_(масалан: 1, 2, 100...)_",
                       parse_mode="Markdown", reply_markup=back_kb())
            return

        elif step == "wait_id":
            if not message.text:
                return
            movie_id = message.text.strip()
            try:
                bot.delete_message(cid, message.message_id)
            except Exception:
                pass
            if movie_id in db:
                send_clean(cid,
                           f"⚠️ ID `{movie_id}` аллакай вуҷуд дорад! ID-и дигар бигзор:",
                           parse_mode="Markdown", reply_markup=back_kb())
                return
            d = admin_state[uid]["data"]
            db[movie_id] = {
                "name":      d["name"],
                "file_id":   d["file_id"],
                "file_type": d["file_type"]
            }
            save_db(db)
            del admin_state[uid]
            send_clean(cid,
                       f"✅ *{d['name']}* илова шуд!\n🔢 ID: `{movie_id}`",
                       parse_mode="Markdown",
                       reply_markup=main_menu_kb(uid))
            return

        elif step == "wait_del_id":
            if not message.text:
                return
            movie_id = message.text.strip()
            try:
                bot.delete_message(cid, message.message_id)
            except Exception:
                pass
            if movie_id not in db:
                send_clean(cid, f"❌ ID `{movie_id}` ёфт нашуд!",
                           parse_mode="Markdown", reply_markup=back_kb())
            else:
                name = db[movie_id]["name"]
                del db[movie_id]
                save_db(db)
                del admin_state[uid]
                send_clean(cid, f"🗑 *{name}* нест шуд!",
                           parse_mode="Markdown",
                           reply_markup=main_menu_kb(uid))
            return


# ======================== MAIN ========================

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_alive_loop, daemon=True).start()
    print("✅ Bot started (Render mode)...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
