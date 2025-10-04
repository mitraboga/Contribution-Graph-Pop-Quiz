from __future__ import annotations
import logging
import os
import sys
import datetime as dt
import threading
import http.server
import socketserver
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from zoneinfo import ZoneInfo

from quiz_engine import QuizEngine
from storage import (
    init_db, record_result, get_score,
    get_daily_count, inc_daily_count,
    set_notify_time, get_notify_time,
    mark_day_complete, get_streak, set_user_name, get_top_streaks,
    iter_all_notify_prefs,
)
from questions import get_random_qa, QA

import pathlib
load_dotenv(dotenv_path=pathlib.Path(".env"), override=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("commit-quiz-bot")

DAILY_CAP = 5
DEFAULT_TZ = "Asia/Kolkata"

# -------------------- Keep-alive HTTP server for Render free tier --------------------
def _start_keepalive():
    """
    Run a tiny HTTP server in a daemon thread so Render's Web Service stays healthy
    while we use Telegram long-polling. Exposes /, /health, /healthz endpoints.
    """
    port = int(os.environ.get("PORT", "8000"))

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            # keep logs quieter (Render polls health a lot)
            return

        def do_GET(self):
            if self.path in ("/", "/health", "/healthz"):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(404)
                self.end_headers()

    def serve():
        with socketserver.TCPServer(("", port), Handler) as httpd:
            logging.getLogger("commit-quiz-bot").info("Keepalive HTTP on %s", port)
            httpd.serve_forever()

    threading.Thread(target=serve, daemon=True).start()

# -------------------- Data models --------------------
@dataclass
class CurrentQuestion:
    username: str
    text: str
    options: list[int]
    correct_index: int
    date_iso: str

@dataclass
class CSQuestion:
    category: str
    text: str
    options: list[str]
    correct_index: int

engine = QuizEngine()

HELP_TEXT = (
    "👋 *Contribution Graph Pop Quiz*\n\n"
    "Commands:\n"
    "• `/start` — welcome\n"
    "• `/setuser <github-username>` — set your GitHub username (for /quiz)\n"
    "• `/quiz` — GitHub contribution-count question (original)\n"
    "• `/daily` — 5-question CS quiz (DSA, Cloud, Cybersecurity, DevOps, AI/ML, Data Science, General CS)\n"
    "• `/notify HH:MM [Area/City]` — daily reminder time (e.g., `/notify 07:30 Asia/Kolkata`)\n"
    "• `/when` — show your next reminder time\n"
    "• `/unnotify` — disable your daily reminder\n"
    "• `/streak` — show your current/best streak\n"
    "• `/streakboard` — top streaks in this chat\n"
    "• `/score` — overall score (GitHub flow)\n"
    "• `/forcecommit [n] [tag]` — manually trigger n commits (debug graph)\n"
    "• `/help` — this message\n"
)

# -------------------- Helpers --------------------
def safe_zoneinfo(tzname: str) -> ZoneInfo:
    try:
        return ZoneInfo(tzname)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)

def _today_ymd(tzname: str) -> str:
    tz = safe_zoneinfo(tzname)
    return dt.datetime.now(tz=tz).date().isoformat()

def _display_name(u) -> str:
    parts = [u.first_name or ""]
    if u.last_name:
        parts.append(u.last_name)
    return " ".join(p for p in parts if p).strip() or (u.username or f"User {u.id}")

# ---- JobQueue-safe storage for CS questions (so scheduled jobs work) ----
def _store_cs_question(context: ContextTypes.DEFAULT_TYPE, user_id: int, csq: "CSQuestion") -> None:
    # Interactive updates: per-user context.user_data available
    if isinstance(getattr(context, "user_data", None), dict):
        context.user_data["cs_q"] = csq
        return
    # JobQueue: context.user_data is None -> store in application.user_data[user_id]
    try:
        app_ud = context.application.user_data  # type: ignore[attr-defined]
    except Exception:
        app_ud = None
    if isinstance(app_ud, dict):
        bucket = app_ud.setdefault(user_id, {})
        bucket["cs_q"] = csq
    else:
        logger.warning("Could not persist cs_q (no user_data/app.user_data available).")

def _load_cs_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional["CSQuestion"]:
    csq = None
    if isinstance(getattr(context, "user_data", None), dict):
        csq = context.user_data.get("cs_q")
    if csq is None:
        try:
            user_id = update.effective_user.id
            app_ud = context.application.user_data  # type: ignore[attr-defined]
            if isinstance(app_ud, dict):
                csq = app_ud.get(user_id, {}).get("cs_q")
        except Exception:
            pass
    return csq

# -------------------- GitHub quiz (original mode) --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    await update.message.reply_text(
        "Welcome to *Contribution Graph Pop Quiz*! 🎯\n\n"
        "GitHub mode: `/setuser <username>` then `/quiz`\n"
        "CS Daily mode: `/daily` (5 questions/day). Set reminder with `/notify HH:MM [TZ]`.\n",
        parse_mode=ParseMode.MARKDOWN,
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)

async def setuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    if not context.args:
        await update.message.reply_text("Usage: `/setuser <github-username>`", parse_mode=ParseMode.MARKDOWN)
        return
    username = context.args[0].strip()
    try:
        _ = engine.load_user_year(username)
    except Exception:
        await update.message.reply_text(
            "❌ Couldn't validate that username via the contributions graph. "
            "Please check the spelling (case-sensitive) and try again.",
        )
        return
    context.user_data["username"] = username
    await update.message.reply_text(
        f"✅ Saved GitHub username: *{username}*\nUse `/quiz` to begin!",
        parse_mode=ParseMode.MARKDOWN
    )

def _format_options(options: list[int]) -> InlineKeyboardMarkup:
    buttons = []
    labels = ["A", "B", "C", "D"]
    row = []
    for i, (label, val) in enumerate(zip(labels, options)):
        row.append(InlineKeyboardButton(f"{label}: {val}", callback_data=f"opt:{i}"))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⏭ Next question", callback_data="next")])
    return InlineKeyboardMarkup(buttons)

async def _ask_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE, username: str):
    q = engine.make_question(username)
    context.user_data["current_q"] = CurrentQuestion(
        username=username,
        text=q.text,
        options=q.options,
        correct_index=q.correct_index,
        date_iso=q.date.isoformat(),
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🧩 *{q.text}*\n\nPick one:",
        reply_markup=_format_options(q.options),
        parse_mode=ParseMode.MARKDOWN,
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    username = context.user_data.get("username")
    if not username:
        await update.message.reply_text("First set your GitHub username: `/setuser <username>`", parse_mode=ParseMode.MARKDOWN)
        return
    await _ask_question(update.effective_chat.id, context, username)

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    correct, total = get_score(update.effective_chat.id, update.effective_user.id)
    if total == 0:
        await update.message.reply_text("You haven't answered any questions yet. Use `/quiz` to start!")
    else:
        await update.message.reply_text(f"📊 Score: *{correct} / {total}* correct.", parse_mode=ParseMode.MARKDOWN)

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_user_name(query.message.chat_id, query.from_user.id, _display_name(query.from_user))
    data = query.data

    current: Optional[CurrentQuestion] = context.user_data.get("current_q")
    if not current:
        await query.edit_message_text("Session expired. Use `/quiz` to start a new question.")
        return

    if data == "next":
        await _ask_question(update.effective_chat.id, context, current.username)
        return

    if not data.startswith("opt:"):
        await query.edit_message_text("Invalid action. Use `/quiz` to start again.")
        return

    try:
        idx = int(data.split(":")[1])
    except ValueError:
        await query.edit_message_text("Invalid option. Use `/quiz` to start again.")
        return

    is_correct = (idx == current.correct_index)
    record_result(update.effective_chat.id, update.effective_user.id, is_correct)

    verdict = "✅ Correct!" if is_correct else f"❌ Incorrect. The right answer was *{current.options[current.correct_index]}*."
    explain = f"_GitHub contributions on {current.date_iso}_"
    await query.edit_message_text(
        text=f"{verdict}\n\n{explain}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_format_options(current.options),
    )

# -------------------- CS Daily quiz --------------------
def _format_cs_options(options: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    labels = ["A", "B", "C", "D"]
    row = []
    for i, (label, val) in enumerate(zip(labels, options)):
        row.append(InlineKeyboardButton(f"{label}: {val}", callback_data=f"cs:opt:{i}"))
        if (i + 1) % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⏭ Next question", callback_data="cs:next")])
    return InlineKeyboardMarkup(buttons)

async def _ask_cs_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE, tzname: str, user_id: Optional[int] = None):
    qa: QA = get_random_qa()
    csq = CSQuestion(
        category=qa.category,
        text=qa.question,
        options=qa.options,
        correct_index=qa.correct_index,
    )

    if user_id is None:
        try:
            user_id = context.update.effective_user.id  # type: ignore[attr-defined]
        except Exception:
            user_id = None
    if user_id is not None:
        _store_cs_question(context, user_id, csq)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🧠 *{csq.category}*: {csq.text}",
        reply_markup=_format_cs_options(csq.options),
        parse_mode=ParseMode.MARKDOWN,
    )

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    prefs = get_notify_time(update.effective_chat.id, update.effective_user.id)
    tzname = prefs[2] if prefs else DEFAULT_TZ
    today = _today_ymd(tzname)
    answered = get_daily_count(update.effective_chat.id, update.effective_user.id, today)
    if answered >= DAILY_CAP:
        st, best, _ = get_streak(update.effective_chat.id, update.effective_user.id)
        await update.message.reply_text(f"🎉 You've completed today's {DAILY_CAP}. Streak: *{st}* (best *{best}*). See you tomorrow!")
        return
    await _ask_cs_question(update.effective_chat.id, context, tzname, user_id=update.effective_user.id)

async def cs_cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    set_user_name(query.message.chat_id, query.from_user.id, _display_name(query.from_user))
    data = query.data

    prefs = get_notify_time(update.effective_chat.id, update.effective_user.id)
    tzname = prefs[2] if prefs else DEFAULT_TZ
    today = _today_ymd(tzname)

    csq: Optional[CSQuestion] = _load_cs_question(update, context)
    if not csq:
        await query.edit_message_text("Session expired. Use `/daily` to start again.")
        return

    if data == "cs:next":
        count_now = get_daily_count(update.effective_chat.id, update.effective_user.id, today)
        if count_now >= DAILY_CAP:
            st, best, _ = get_streak(update.effective_chat.id, update.effective_user.id)
            await query.edit_message_text(f"🎉 Done for today — {DAILY_CAP}/{DAILY_CAP}. Streak: *{st}* (best *{best}*).")
            return
        await _ask_cs_question(update.effective_chat.id, context, tzname, user_id=update.effective_user.id)
        return

    if not data.startswith("cs:opt:"):
        await query.edit_message_text("Invalid action. Use `/daily` to start again.")
        return

    try:
        idx = int(data.split(":")[2])
    except ValueError:
        await query.edit_message_text("Invalid option. Use `/daily` to start again.")
        return

    is_correct = (idx == csq.correct_index)
    count_after = inc_daily_count(update.effective_chat.id, update.effective_user.id, today)

    streak_msg = ""
    if count_after >= DAILY_CAP:
        streak, best, _ = mark_day_complete(update.effective_chat.id, update.effective_user.id, today)
        streak_msg = f"\n\n🔥 *Streak*: {streak} day(s) (best {best})"

        # Trigger 5 commits when the day’s 5 Qs are done
        try:
            from github_committer import make_daily_commits_if_configured
            tag = str(update.effective_user.id)
            info = make_daily_commits_if_configured(n=5, tag=tag)
            if info:
                logger.info(info)
        except Exception as e:
            logger.exception("GitHub commit failed", exc_info=e)

    verdict = "✅ Correct!" if is_correct else f"❌ Incorrect. The right answer was *{csq.options[csq.correct_index]}*."
    footer = f"Progress today: {min(count_after, DAILY_CAP)} / {DAILY_CAP}{streak_msg}"
    await query.edit_message_text(
        text=f"{verdict}\n\n_{csq.category}_\n\n{footer}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_format_cs_options(csq.options),
    )

# -------------------- Daily reminder scheduling --------------------
async def _daily_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    user_id = job.data["user_id"]
    tzname = job.data["tz"]
    today = _today_ymd(tzname)
    answered = get_daily_count(chat_id, user_id, today)
    if answered >= DAILY_CAP:
        return
    await _ask_cs_question(chat_id, context, tzname, user_id=user_id)

def _reschedule_all_jobs(app: Application):
    """
    Recreate all daily reminder jobs from DB (so jobs survive bot restarts/redeploys).
    """
    if app.job_queue is None:
        logger.error('JobQueue not available. Install PTB with: pip install "python-telegram-bot[job-queue]"')
        return

    # Remove existing daily-* jobs to avoid duplicates
    for j in list(app.job_queue.jobs()):
        if j.name and j.name.startswith("daily-"):
            j.schedule_removal()

    from datetime import time as dtime
    total = 0
    for chat_id, user_id, hour, minute, tzname in iter_all_notify_prefs():
        tz = safe_zoneinfo(tzname)
        job_name = f"daily-{chat_id}-{user_id}"
        app.job_queue.run_daily(
            _daily_job,
            time=dtime(hour=hour, minute=minute, tzinfo=tz),
            name=job_name,
            chat_id=chat_id,
            data={"user_id": user_id, "tz": tzname},
        )
        total += 1
    logger.info("Rescheduled %d daily reminder job(s) from DB.", total)

# -------------------- /notify + /when + /unnotify --------------------
async def notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /notify HH:MM [Area/City]  e.g., /notify 07:30 Asia/Kolkata
    Sets a daily reminder + sends a 2s test question to confirm it's armed.
    """
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    if not context.args:
        await update.message.reply_text(
            "Usage: `/notify HH:MM [Area/City]`\nExample: `/notify 07:30 Asia/Kolkata`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    time_part = context.args[0]
    tzname = context.args[1] if len(context.args) > 1 else DEFAULT_TZ

    try:
        hour, minute = map(int, time_part.split(":"))
        assert 0 <= hour <= 23 and 0 <= minute <= 59
        tz = safe_zoneinfo(tzname)
    except Exception:
        await update.message.reply_text(
            "❌ Invalid time or timezone. Example: `/notify 07:30 Asia/Kolkata`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    set_notify_time(update.effective_chat.id, update.effective_user.id, hour, minute, tzname)

    app: Application = context.application
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    job_name = f"daily-{chat_id}-{user_id}"

    if app.job_queue is None:
        logger.error('python-telegram-bot[job-queue] is not installed. '
                     'Run: pip install "python-telegram-bot[job-queue]"')
        await update.message.reply_text("🚫 Job queue not available. Please install PTB with job-queue extra.")
        return
    for j in app.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()

    now = dt.datetime.now(tz=tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + dt.timedelta(days=1)

    from datetime import time as dtime
    app.job_queue.run_daily(
        _daily_job,
        time=dtime(hour=hour, minute=minute, tzinfo=tz),
        name=job_name,
        chat_id=chat_id,
        data={"user_id": user_id, "tz": tzname},
    )

    app.job_queue.run_once(
        _daily_job,
        when=2,
        name=f"test-{job_name}",
        chat_id=chat_id,
        data={"user_id": user_id, "tz": tzname},
    )

    pretty_next = target.strftime("%Y-%m-%d %H:%M")
    await update.message.reply_text(
        f"⏰ Daily reminder set for *{hour:02d}:{minute:02d}* ({tzname}).\n"
        f"Next run: *{pretty_next}* {tzname}\n"
        f"✅ I’ll send a test question in ~2s to confirm.",
        parse_mode=ParseMode.MARKDOWN,
    )

async def when_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    prefs = get_notify_time(update.effective_chat.id, update.effective_user.id)
    if not prefs:
        await update.message.reply_text("No reminder set. Use `/notify HH:MM [Area/City]` first.", parse_mode=ParseMode.MARKDOWN)
        return

    hour, minute, tzname = prefs
    tz = safe_zoneinfo(tzname)
    now = dt.datetime.now(tz=tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + dt.timedelta(days=1)

    await update.message.reply_text(
        f"🗓️ Next reminder: *{target.strftime('%Y-%m-%d %H:%M')}* ({tzname})",
        parse_mode=ParseMode.MARKDOWN,
    )

async def unnotify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    app: Application = context.application
    if app.job_queue is None:
        await update.message.reply_text("No active daily reminder to cancel (job queue unavailable).")
        return
    job_name = f"daily-{update.effective_chat.id}-{update.effective_user.id}"

    removed = False
    for j in app.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()
        removed = True

    if removed:
        await update.message.reply_text("🛑 Daily reminder disabled.")
    else:
        await update.message.reply_text("No active daily reminder to cancel.")

# -------------------- Streaks --------------------
async def streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    st, best, last = get_streak(update.effective_chat.id, update.effective_user.id)
    if st == 0:
        await update.message.reply_text("No streak yet — answer all 5 `/daily` questions today to start a streak! 🔥")
    else:
        last_text = f" (last completed: {last})" if last else ""
        await update.message.reply_text(f"🔥 *Streak*: {st} day(s) — *Best*: {best}{last_text}", parse_mode=ParseMode.MARKDOWN)

async def streakboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    rows = get_top_streaks(update.effective_chat.id, limit=10)
    if not rows:
        await update.message.reply_text("No streaks yet in this chat. Be the first: complete `/daily` today!")
        return
    lines = ["🏆 *Top Streaks*"]
    for i, (uid, st, best, name) in enumerate(rows, start=1):
        lines.append(f"{i}. {name}: *{st}* (best {best})")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# -------------------- Force commits --------------------
async def forcecommit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_name(update.effective_chat.id, update.effective_user.id, _display_name(update.effective_user))
    n = 1
    tag = str(update.effective_user.id)
    if len(context.args) >= 1:
        try:
            n = max(1, int(context.args[0]))
        except ValueError:
            await update.message.reply_text("Usage: `/forcecommit [n] [tag]`  (n must be an integer)", parse_mode=ParseMode.MARKDOWN)
            return
    if len(context.args) >= 2:
        tag = context.args[1]

    try:
        from github_committer import make_daily_commits_if_configured
        info = make_daily_commits_if_configured(n=n, tag=tag)
        await update.message.reply_text(info or "No result returned.")
        logger.info("forcecommit: %s", info)
    except Exception as e:
        logger.exception("forcecommit error", exc_info=e)
        await update.message.reply_text(f"Commit failed: {e}")

# -------------------- Entrypoint --------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Contribution Graph Pop Quiz Bot")
    parser.add_argument("--webhook", action="store_true", help="Enable webhook mode (default polling)")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", ""), help="Public base URL for webhook")
    parser.add_argument("--path", default=os.environ.get("WEBHOOK_PATH", "/webhook"), help="Webhook path")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")), help="Port to listen on")
    parser.add_argument("--listen", default=os.environ.get("LISTEN", "0.0.0.0"), help="Host to bind")
    args = parser.parse_args()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.error("Missing BOT_TOKEN. Set it in the environment or .env file.")
        sys.exit(1)

    # Start the tiny HTTP server for Render health checks/keepalive
    _start_keepalive()

    # Ensure DB exists/migrated
    init_db()

    # Build PTB app (polling)
    application = (
        Application.builder()
        .token(token)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("setuser", setuser))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("score", score))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("notify", notify))
    application.add_handler(CommandHandler("when", when_cmd))
    application.add_handler(CommandHandler("unnotify", unnotify))
    application.add_handler(CommandHandler("streak", streak))
    application.add_handler(CommandHandler("streakboard", streakboard))
    application.add_handler(CommandHandler("forcecommit", forcecommit))

    # Callbacks
    application.add_handler(CallbackQueryHandler(cb_handler, pattern=r"^(opt:|next$)"))
    application.add_handler(CallbackQueryHandler(cs_cb_handler, pattern=r"^cs:"))

    # Rebuild daily jobs from DB so schedules persist across restarts/redeploys
    _reschedule_all_jobs(application)

    # Polling mode (simple, reliable on Render with our keepalive)
    logger.info("Starting in polling mode")
    application.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
