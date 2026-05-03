"""
FOCUS JIT Fellowship Bot
=========================
F = Fellowship
O = Of
C = Christian
U = University
S = Students
JIT = (your campus chapter)

Features:
  • Admin/leader broadcasts to ALL members at once (stored usernames, never re-typed)
  • Team-specific broadcasts (message reaches only that team)
  • Charis Place – shared space for ideas, bible study, coffee, prayer, worship
  • Prayer requests → prayer team only → member communicates privately with prayer team
  • Daily verse scheduled every morning at 7:00 AM (managed by Bible Study team)
  • Wednesday program announcements
  • Event promotions
  • Feedback channel
  • Weekly Bible challenge with streaks & leaderboard
  • Admin panel hidden from regular members

Teams:
  Prayer, Choir, Leaders, Bible Study, Council, Natan, Tech,
  Voluntary, Worship, Charis, MBS, Finance, Post Graduate

Setup:
  1. pip install python-telegram-bot apscheduler
  2. Set BOT_TOKEN below (from @BotFather)
  3. Set ADMIN_IDS below (get your numeric ID from @userinfobot)
  4. Run the bot; send a message in your group to get GROUP_CHAT_ID printed in console
  5. Set GROUP_CHAT_ID below and restart
"""

import os
import logging
import json
import random
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ─────────────────────────────────────────────────────────────────
#  ★  CONFIGURATION  — Edit these before running  ★
# ─────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "8646956853:AAHvsjf_kJA-vGgNM32W0NxmL9pxxFt59jc")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "YOUR_GROUP_CHAT_ID_HERE")

# Numeric Telegram user IDs of leaders/admins.
# Get yours by messaging @userinfobot on Telegram.
ADMIN_IDS = {
    838712052,   # ← Replace with real admin IDs
    8097004980,
}

TIMEZONE = "Africa/Addis_Ababa"

# ─────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
#  ALL VALID TEAMS
# ─────────────────────────────────────────────────────────────────
ALL_TEAMS = [
    "prayer", "choir", "leaders", "bible_study", "council",
    "natan", "tech", "voluntary", "worship", "charis",
    "mbs", "finance", "post_graduate",
]

TEAM_DISPLAY = {
    "prayer":        "🙏 Prayer Team",
    "choir":         "🎵 Choir Team",
    "leaders":       "👑 Leaders",
    "bible_study":   "📖 Bible Study Team",
    "council":       "🏛️ Council Team",
    "natan":         "🤝 Natan Team",
    "tech":          "💻 Tech Team",
    "voluntary":     "🤲 Voluntary Team",
    "worship":       "🎸 Worship Team",
    "charis":        "☕ Charis Team",
    "mbs":           "📚 MBS Team",
    "finance":       "💰 Finance Team",
    "post_graduate": "🎓 Post Graduate Team",
}

# ─────────────────────────────────────────────────────────────────
#  IN-MEMORY DATABASE  (replace with SQLite/Firebase for persistence)
# ─────────────────────────────────────────────────────────────────

# members[user_id] = {
#   "name": str, "username": str, "teams": [str, ...], "chat_id": int
# }
members: dict = {}

# prayer_requests[request_id] = {
#   "text": str, "requester_id": int, "requester_name": str,
#   "assigned_prayer_member_id": int|None, "active": bool
# }
prayer_requests: dict = {}
_prayer_request_counter = 0

# events list
events: list = []

# charis contributions
charis_posts: list = []

# weekly challenge responses & streaks
challenge_responses: dict = {}
streaks: dict = {}

# conversation states
(BROADCAST_MSG, TEAMCAST_TEAM, TEAMCAST_MSG,
 ADDMEMBER_ID, ADDMEMBER_TEAMS,
 REMOVEMEMBER_ID,
 WEDNESDAY_MSG, ADDEVENT_DATA,
 PRAYREPLY_ID, PRAYREPLY_MSG,
 CHARIS_MSG, FEEDBACK_MSG,
 PRAY_MSG) = range(13)

# ─────────────────────────────────────────────────────────────────
#  DAILY VERSES  (managed by Bible Study team, hidden label)
# ─────────────────────────────────────────────────────────────────
DAILY_VERSES = [
    {"verse": "For I know the plans I have for you, declares the Lord, plans to prosper you and not to harm you, plans to give you hope and a future.", "ref": "Jeremiah 29:11", "devotional": "God's plans for your life are intentional and good. Even when your path feels uncertain — trust that He is working something beautiful. Surrender one worry to Him today."},
    {"verse": "I can do all this through him who gives me strength.", "ref": "Philippians 4:13", "devotional": "Whatever you face today — a difficult exam, a hard conversation, a moment of doubt — His strength is available to you. Ask for it."},
    {"verse": "Trust in the Lord with all your heart and lean not on your own understanding; in all your ways submit to him, and he will make your paths straight.", "ref": "Proverbs 3:5-6", "devotional": "Our understanding is limited. His is not. Identify one area where you are trusting your own logic more than God's word. Surrender it."},
    {"verse": "Be strong and courageous. Do not be afraid; do not be discouraged, for the Lord your God will be with you wherever you go.", "ref": "Joshua 1:9", "devotional": "Courage is not the absence of fear — it is choosing to move forward in faith despite fear. Walk boldly today."},
    {"verse": "But seek first his kingdom and his righteousness, and all these things will be given to you as well.", "ref": "Matthew 6:33", "devotional": "When we put His kingdom first, He takes responsibility for all the rest. What would your day look like if you sought Him first?"},
    {"verse": "Let your light shine before others, that they may see your good deeds and glorify your Father in heaven.", "ref": "Matthew 5:16", "devotional": "Your kindness, integrity and faith are a testimony. Let one action today point someone to Jesus."},
    {"verse": "Come to me, all you who are weary and burdened, and I will give you rest.", "ref": "Matthew 11:28", "devotional": "Jesus does not say 'fix yourself then come.' He says 'come as you are.' Bring your tiredness to Him today."},
    {"verse": "Do not conform to the pattern of this world, but be transformed by the renewing of your mind.", "ref": "Romans 12:2", "devotional": "God's word reshapes you from the inside. Spend time in Scripture today and let it renew how you see yourself and the world."},
    {"verse": "And we know that in all things God works for the good of those who love him, who have been called according to his purpose.", "ref": "Romans 8:28", "devotional": "All things — including the painful and confusing ones — are being woven into God's good purpose for your life."},
    {"verse": "The Lord is my shepherd, I lack nothing.", "ref": "Psalm 23:1", "devotional": "If the Lord is your shepherd, you are never truly lacking. List three things He has already provided for you this week."},
    {"verse": "Cast all your anxiety on him because he cares for you.", "ref": "1 Peter 5:7", "devotional": "God's care for you is not passive — it is active, personal and constant. Cast your worries like a fisherman casts a net: release them fully."},
    {"verse": "The Lord your God is with you, the Mighty Warrior who saves. He will take great delight in you; in his love he will no longer rebuke you, but will rejoice over you with singing.", "ref": "Zephaniah 3:17", "devotional": "God does not merely tolerate you — He sings over you with joy. Let that truth reshape how you see yourself today."},
    {"verse": "Therefore, if anyone is in Christ, the new creation has come: The old has gone, the new is here!", "ref": "2 Corinthians 5:17", "devotional": "Your identity is not tied to your mistakes or your past. In Christ, you are new. Walk in that newness today."},
    {"verse": "Be still and know that I am God.", "ref": "Psalm 46:10", "devotional": "In a world of noise and deadlines, stillness is an act of faith. Take five minutes today to simply be with God — no agenda, no words, just presence."},
]

WEEKLY_CHALLENGES = [
    {"passage": "Proverbs 3:1-10", "question": "What is one principle from this passage you want to apply to your studies or relationships this week?"},
    {"passage": "Psalm 1", "question": "What does a 'blessed' person look like according to this Psalm? How does your daily routine compare?"},
    {"passage": "Romans 12:1-21", "question": "Verse 2 says 'be transformed by the renewing of your mind.' What one thought pattern do you want God to transform?"},
    {"passage": "Matthew 5:1-16 (The Beatitudes)", "question": "Which Beatitude speaks most to your current season of life and why?"},
    {"passage": "1 Corinthians 13", "question": "Which description of love from this chapter is hardest for you to live out in your fellowship family?"},
    {"passage": "James 1:1-18", "question": "James says to consider it pure joy when you face trials. Share a challenge you are facing and one way to find joy in it."},
    {"passage": "John 15:1-17", "question": "What does it mean to remain in the vine? What is one practical way you will abide in Christ this week?"},
]

# ─────────────────────────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_bible_study(user_id: int) -> bool:
    m = members.get(user_id)
    return m is not None and "bible_study" in m.get("teams", [])

def is_prayer_team(user_id: int) -> bool:
    m = members.get(user_id)
    return m is not None and "prayer" in m.get("teams", [])

def get_team_members(team: str) -> list:
    return [m for m in members.values() if team in m.get("teams", [])]

def get_all_members() -> list:
    return list(members.values())

def get_verse_of_day() -> dict:
    day = datetime.now().timetuple().tm_yday
    return DAILY_VERSES[day % len(DAILY_VERSES)]

def current_week() -> int:
    return datetime.now().isocalendar()[1]

def get_challenge_of_week() -> dict:
    return WEEKLY_CHALLENGES[current_week() % len(WEEKLY_CHALLENGES)]

def next_prayer_id() -> int:
    global _prayer_request_counter
    _prayer_request_counter += 1
    return _prayer_request_counter

def teams_keyboard(selected: list = None, add_done: bool = False):
    """Build an inline keyboard for team selection."""
    selected = selected or []
    buttons = []
    row = []
    for i, team in enumerate(ALL_TEAMS):
        label = TEAM_DISPLAY[team]
        if team in selected:
            label = "✅ " + label
        row.append(InlineKeyboardButton(label, callback_data=f"team_{team}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if add_done:
        buttons.append([InlineKeyboardButton("✅ Done — Save teams", callback_data="teams_done")])
    return InlineKeyboardMarkup(buttons)

# ─────────────────────────────────────────────────────────────────
#  /start  — Member registration
# ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    uid  = user.id

    if uid in members:
        member_menu(update, context)
        return

    # Auto-register the member with no team yet
    members[uid] = {
        "name":     user.full_name,
        "username": user.username or user.full_name,
        "teams":    [],
        "chat_id":  uid,
    }

    text = (
        f"🙏 *Welcome to FOCUS JIT Fellowship Bot, {user.first_name}!*\n\n"
        f"*F*ellowship *O*f *C*hristian *U*niversity *S*tudents\n\n"
        "You are now registered as a member of FOCUS JIT. 🎉\n\n"
        "Here is what you can do:\n\n"
        "📖 /verse — Today's Bible verse\n"
        "📅 /events — Upcoming events\n"
        "☕ /charis — Share at Charis Place\n"
        "🙏 /pray — Request individual prayer\n"
        "💬 /feedback — Send feedback to leadership\n"
        "📚 /challenge — This week's Bible challenge\n"
        "🏆 /leaderboard — Fellowship streaks\n"
        "🔥 /streak — Your challenge streak\n"
        "👥 /myteams — See which teams you are in\n\n"
        "God bless you! ✝️"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def member_menu(update, context):
    pass  # Already registered — no duplicate message needed


# ─────────────────────────────────────────────────────────────────
#  /myteams
# ─────────────────────────────────────────────────────────────────

async def myteams_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid not in members:
        await update.message.reply_text("Please send /start to register first.")
        return
    m = members[uid]
    if not m["teams"]:
        await update.message.reply_text(
            "👥 You are not assigned to any team yet.\n"
            "Your fellowship leaders will assign you to a team."
        )
        return
    team_names = "\n".join(f"• {TEAM_DISPLAY.get(t, t)}" for t in m["teams"])
    await update.message.reply_text(
        f"👥 *Your Teams*\n\n{team_names}",
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────────────────────────
#  /verse  — On-demand Bible verse
# ─────────────────────────────────────────────────────────────────

async def verse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    v = get_verse_of_day()
    text = (
        f"📖 *Verse of the Day*\n\n"
        f"_{v['verse']}_\n\n"
        f"— *{v['ref']}*\n\n"
        f"✍️ *Reflection:*\n{v['devotional']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────
#  /events  — View upcoming events
# ─────────────────────────────────────────────────────────────────

async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now()
    upcoming = sorted([e for e in events if e["datetime"] > now], key=lambda x: x["datetime"])
    if not upcoming:
        await update.message.reply_text(
            "📅 No upcoming events right now.\n"
            "Check back soon — the leadership will announce new events!"
        )
        return
    lines = ["📅 *Upcoming FOCUS JIT Events*\n"]
    for e in upcoming[:5]:
        dt_str = e["datetime"].strftime("%A, %B %d at %I:%M %p")
        lines.append(f"📌 *{e['title']}*")
        lines.append(f"   🕒 {dt_str}")
        lines.append(f"   📍 {e['location']}")
        if e.get("description"):
            lines.append(f"   📝 {e['description']}")
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────
#  /charis  — Charis Place: share ideas, bible study, worship, coffee
# ─────────────────────────────────────────────────────────────────

async def charis_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if uid not in members:
        await update.message.reply_text("Please send /start to register first.")
        return ConversationHandler.END
    await update.message.reply_text(
        "☕ *Welcome to Charis Place!*\n\n"
        "_Charis_ is your fellowship family space for sharing ideas, "
        "doing Bible study together, praying, worshipping, and having coffee time. ✝️☕\n\n"
        "What would you like to share with the fellowship today?\n\n"
        "Type your message and it will be shared to the group:\n\n"
        "(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    return CHARIS_MSG


async def charis_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    charis_posts.append({"author": user.full_name, "text": text, "time": datetime.now()})

    msg = (
        f"☕ *Charis Place — Shared by {user.first_name}*\n\n"
        f"{text}\n\n"
        f"✝️ _FOCUS JIT Fellowship_"
    )
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg, parse_mode="Markdown")
        await update.message.reply_text("✅ Your message has been shared at Charis Place! 🙌")
    except Exception as e:
        logger.error(f"Charis error: {e}")
        await update.message.reply_text("❌ Could not send to group. Ask your tech team to check the GROUP_CHAT_ID.")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────
#  /feedback
# ─────────────────────────────────────────────────────────────────

async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if uid not in members:
        await update.message.reply_text("Please send /start to register first.")
        return ConversationHandler.END
    await update.message.reply_text(
        "💬 *Fellowship Feedback*\n\n"
        "Share your thoughts, suggestions, or concerns about FOCUS JIT.\n"
        "Your feedback goes directly to the leadership team.\n\n"
        "Type your feedback now:\n(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    return FEEDBACK_MSG


async def feedback_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    msg = (
        f"📩 *New Feedback from {user.full_name}*\n"
        f"(@{user.username or 'no username'})\n\n"
        f"{text}"
    )
    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=msg, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    if sent > 0:
        await update.message.reply_text("✅ Thank you! Your feedback has been sent to the leadership team. 🙏")
    else:
        await update.message.reply_text("⚠️ Could not reach leaders right now. Please try again later.")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────
#  /pray  — Individual prayer request → Prayer Team only
# ─────────────────────────────────────────────────────────────────

async def pray_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if uid not in members:
        await update.message.reply_text("Please send /start to register first.")
        return ConversationHandler.END
    await update.message.reply_text(
        "🙏 *Individual Prayer Request*\n\n"
        "Your request will be sent privately to the *Prayer Team*.\n"
        "They will reach out to you directly — your request is confidential. 🤍\n\n"
        "Type your prayer request now:\n(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    return PRAY_MSG


async def pray_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    req_id = next_prayer_id()

    prayer_requests[req_id] = {
        "text":              text,
        "requester_id":      user.id,
        "requester_name":    user.full_name,
        "requester_username": user.username or user.full_name,
        "active":            True,
    }

    prayer_team = get_team_members("prayer")
    if not prayer_team:
        await update.message.reply_text(
            "🙏 Your request has been recorded. The prayer team will be in touch soon. God hears you! 🤍"
        )
        return ConversationHandler.END

    notified = 0
    for pt_member in prayer_team:
        try:
            msg = (
                f"🙏 *New Individual Prayer Request*\n\n"
                f"From: {user.full_name} (@{user.username or 'no username'})\n\n"
                f"Request:\n_{text}_\n\n"
                f"Please reply directly to this member to pray with them.\n"
                f"Use /prayreply {req_id} to mark it and communicate.\n\n"
                f"Request ID: #{req_id}"
            )
            await context.bot.send_message(
                chat_id=pt_member["chat_id"],
                text=msg,
                parse_mode="Markdown"
            )
            notified += 1
        except Exception as e:
            logger.error(f"Pray notify error: {e}")

    if notified > 0:
        await update.message.reply_text(
            "🙏 *Your prayer request has been received!*\n\n"
            "The Prayer Team has been notified and will contact you personally very soon.\n\n"
            "You are not alone — God hears every prayer. 🤍✝️",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🙏 Your request is recorded. The prayer team will reach out to you. God hears you! 🤍"
        )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────
#  /prayreply  — Prayer team replies to a member
# ─────────────────────────────────────────────────────────────────

async def prayreply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if not is_prayer_team(uid):
        await update.message.reply_text("⛔ This command is for the Prayer Team only.")
        return ConversationHandler.END

    if context.args:
        context.user_data["prayreply_id"] = int(context.args[0])
        await update.message.reply_text(
            f"🙏 Replying to prayer request #{context.args[0]}.\n\n"
            "Type your message for the member:\n(Type /cancel to cancel)"
        )
        return PRAYREPLY_MSG
    else:
        # List active prayer requests
        active = {k: v for k, v in prayer_requests.items() if v.get("active")}
        if not active:
            await update.message.reply_text("✅ No active prayer requests right now.")
            return ConversationHandler.END
        lines = ["🙏 *Active Prayer Requests*\n"]
        for req_id, req in active.items():
            lines.append(f"#{req_id} — {req['requester_name']}: _{req['text'][:60]}..._")
        lines.append("\nReply using: /prayreply [request_id]")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return ConversationHandler.END


async def prayreply_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    req_id = context.user_data.get("prayreply_id")

    if not req_id or req_id not in prayer_requests:
        await update.message.reply_text("❌ Prayer request not found. Use /prayreply to list requests.")
        return ConversationHandler.END

    req = prayer_requests[req_id]
    msg = (
        f"🙏 *Message from the Prayer Team*\n\n"
        f"Regarding your prayer request: _{req['text'][:80]}..._\n\n"
        f"{text}\n\n"
        f"— {user.full_name} (Prayer Team) ✝️\n\n"
        f"You may reply directly to {user.first_name} for further prayer support."
    )
    try:
        await context.bot.send_message(
            chat_id=req["requester_id"],
            text=msg,
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Your message has been sent to {req['requester_name']}. 🙏")
    except Exception as e:
        await update.message.reply_text(f"❌ Could not reach the member. They may need to start the bot first.")
        logger.error(f"prayreply error: {e}")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────
#  WEEKLY BIBLE CHALLENGE  (streak system)
# ─────────────────────────────────────────────────────────────────

async def challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ch = get_challenge_of_week()
    week = current_week()
    text = (
        f"📚 *This Week's Bible Challenge* — Week {week}\n\n"
        f"📖 Read: *{ch['passage']}*\n\n"
        f"💭 Question: _{ch['question']}_\n\n"
        f"Reply to this message in the group with your answer by Sunday and earn a streak point! 🏆\n\n"
        "Use /streak to see your current streak."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def respond_to_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    if not message.reply_to_message:
        return
    original_text = message.reply_to_message.text or ""
    if "Bible Challenge" not in original_text:
        return
    week = current_week()
    uid = user.id
    if uid in challenge_responses and challenge_responses[uid].get("week") == week:
        await message.reply_text(f"✅ {user.first_name}, your response for this week is already saved!")
        return
    challenge_responses[uid] = {"name": user.first_name, "response": message.text, "week": week}
    if uid not in streaks:
        streaks[uid] = {"name": user.first_name, "count": 0, "last_week": 0}
    if streaks[uid]["last_week"] == week - 1:
        streaks[uid]["count"] += 1
    else:
        streaks[uid]["count"] = 1
    streaks[uid]["last_week"] = week
    streaks[uid]["name"] = user.first_name
    count = streaks[uid]["count"]
    badge = "🔥" * min(count, 5)
    await message.reply_text(
        f"🎉 *{user.first_name}*, your response has been recorded!\n\n"
        f"Current streak: *{count} week{'s' if count > 1 else ''}* {badge}\n\n"
        "Keep it up — consistency is how we grow! 📖",
        parse_mode="Markdown"
    )


async def streak_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    user = update.effective_user
    if uid not in streaks or streaks[uid]["count"] == 0:
        await update.message.reply_text(
            "📊 You have not completed any weekly challenges yet!\n\n"
            "Use /challenge to start your streak. 🔥"
        )
        return
    s = streaks[uid]
    badge = "🔥" * min(s["count"], 5)
    await update.message.reply_text(
        f"🏆 *{user.first_name}'s Streak*\n\n"
        f"Current streak: *{s['count']} week{'s' if s['count'] > 1 else ''}* {badge}\n\n"
        "Keep responding to weekly challenges to grow your streak! 📖",
        parse_mode="Markdown"
    )


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not streaks:
        await update.message.reply_text(
            "🏆 The leaderboard is empty.\n\nComplete weekly Bible challenges to appear here! Use /challenge to start. 📖"
        )
        return
    sorted_streaks = sorted(streaks.values(), key=lambda x: x["count"], reverse=True)
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 *FOCUS JIT — Leaderboard*\n"]
    for i, s in enumerate(sorted_streaks[:10]):
        badge = "🔥" * min(s["count"], 5)
        lines.append(f"{medals[i]} {s['name']} — {s['count']} week{'s' if s['count'] > 1 else ''} {badge}")
    lines.append("\nKeep reading, keep growing! 📖")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ─────────────────────────────────────────────────────────────────
#  ══════════════  ADMIN / LEADER COMMANDS  ══════════════
#  These are hidden from the regular member menu.
# ─────────────────────────────────────────────────────────────────

async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if user is admin, False otherwise (sends error message)."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ This command is for fellowship leaders only.")
        return False
    return True


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel — shows all leader commands."""
    if not await admin_only(update, context):
        return
    text = (
        "👑 *FOCUS JIT — Leader / Admin Panel*\n\n"
        "📢 *Broadcast & Announcements:*\n"
        "/broadcast — Send message to ALL members\n"
        "/teamcast — Send message to a specific team\n"
        "/wednesday — Announce Wednesday program\n"
        "/addevent — Add an event\n\n"
        "👥 *Member Management:*\n"
        "/addmember — Add a member & assign teams\n"
        "/removemember — Remove a member\n"
        "/members — View all members & their teams\n\n"
        "📖 *Bible Study Tools:*\n"
        "/sendverse — Send daily verse now (Bible Study team)\n\n"
        "📊 *Overview:*\n"
        "/stats — Fellowship statistics\n\n"
        "🔒 _This panel is visible to leaders only._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── BROADCAST ──────────────────────────────────────────────────

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 *Broadcast to ALL Members*\n\n"
        f"There are currently *{len(members)}* registered members.\n\n"
        "Type your message and it will be delivered to every member at once:\n\n"
        "(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    return BROADCAST_MSG


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    msg = (
        f"📣 *FOCUS JIT Fellowship Announcement*\n\n"
        f"{text}\n\n"
        f"— {user.full_name} (Leadership) ✝️"
    )
    sent, failed = 0, 0
    for m in get_all_members():
        try:
            await context.bot.send_message(chat_id=m["chat_id"], text=msg, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

    # Also post to group
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Broadcast delivered!\n"
        f"• Sent to: {sent} members\n"
        f"• Failed: {failed} (members who haven't started the bot)"
    )
    return ConversationHandler.END


# ── TEAMCAST ───────────────────────────────────────────────────

async def teamcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await admin_only(update, context):
        return ConversationHandler.END
    keyboard = []
    row = []
    for team in ALL_TEAMS:
        count = len(get_team_members(team))
        row.append(InlineKeyboardButton(
            f"{TEAM_DISPLAY[team]} ({count})",
            callback_data=f"cast_{team}"
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    await update.message.reply_text(
        "📨 *Team Broadcast — Select a Team*\n\n"
        "Which team should receive this message?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TEAMCAST_TEAM


async def teamcast_team_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    team = query.data.replace("cast_", "")
    context.user_data["teamcast_team"] = team
    count = len(get_team_members(team))
    await query.edit_message_text(
        f"📨 Sending to: *{TEAM_DISPLAY.get(team, team)}* ({count} members)\n\n"
        "Type your message for this team:\n(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    return TEAMCAST_MSG


async def teamcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    team = context.user_data.get("teamcast_team")
    team_members = get_team_members(team)
    if not team_members:
        await update.message.reply_text(f"⚠️ No members in {TEAM_DISPLAY.get(team, team)} yet.")
        return ConversationHandler.END

    msg = (
        f"📨 *Message for {TEAM_DISPLAY.get(team, team)}*\n\n"
        f"{text}\n\n"
        f"— {user.full_name} (Leadership) ✝️"
    )
    sent, failed = 0, 0
    for m in team_members:
        try:
            await context.bot.send_message(chat_id=m["chat_id"], text=msg, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Team message delivered to *{TEAM_DISPLAY.get(team, team)}*!\n"
        f"• Sent: {sent}\n• Failed: {failed}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ── WEDNESDAY PROGRAM ──────────────────────────────────────────

async def wednesday_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "🗓️ *Wednesday Program Announcement*\n\n"
        "Type the details for this Wednesday's program.\n"
        "It will be sent to all fellowship members:\n\n"
        "(Type /cancel to cancel)"
    )
    return WEDNESDAY_MSG


async def wednesday_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    msg = (
        f"🗓️ *FOCUS JIT — Wednesday Program*\n\n"
        f"{text}\n\n"
        f"See you there! 🙌✝️\n"
        f"— {user.full_name} (Leadership)"
    )
    sent = 0
    for m in get_all_members():
        try:
            await context.bot.send_message(chat_id=m["chat_id"], text=msg, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception:
        pass
    await update.message.reply_text(f"✅ Wednesday program announcement sent to {sent} members!")
    return ConversationHandler.END


# ── ADD EVENT ──────────────────────────────────────────────────

async def addevent_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "📅 *Add a New Event*\n\n"
        "Send event details in this format:\n\n"
        "`Title | YYYY-MM-DD HH:MM | Location | Description`\n\n"
        "Example:\n"
        "`Sunday Service | 2025-06-01 09:00 | Main Hall | Come ready to worship!`\n\n"
        "(Type /cancel to cancel)",
        parse_mode="Markdown"
    )
    return ADDEVENT_DATA


async def addevent_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    args_text = update.message.text
    if "|" not in args_text:
        await update.message.reply_text("❌ Please use the format: Title | YYYY-MM-DD HH:MM | Location | Description")
        return ADDEVENT_DATA
    parts = [p.strip() for p in args_text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ Need at least: Title | Date & Time | Location")
        return ADDEVENT_DATA
    title = parts[0]
    date_str = parts[1]
    location = parts[2]
    description = parts[3] if len(parts) > 3 else ""
    try:
        event_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Date format incorrect. Use: YYYY-MM-DD HH:MM")
        return ADDEVENT_DATA

    events.append({"title": title, "datetime": event_dt, "location": location, "description": description})

    # Announce to all members
    msg = (
        f"📌 *New Event from FOCUS JIT Leadership!*\n\n"
        f"🎉 *{title}*\n"
        f"🕒 {event_dt.strftime('%A, %B %d at %I:%M %p')}\n"
        f"📍 {location}\n"
        f"{'📝 ' + description if description else ''}\n\n"
        "Mark your calendar! See you there. 🙌✝️"
    )
    sent = 0
    for m in get_all_members():
        try:
            await context.bot.send_message(chat_id=m["chat_id"], text=msg, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ Event added and announced to {sent} members!\n\n"
        f"📌 *{title}*\n"
        f"🕒 {event_dt.strftime('%A, %B %d at %I:%M %p')}\n"
        f"📍 {location}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ── ADD MEMBER ─────────────────────────────────────────────────

async def addmember_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "👤 *Add a Member*\n\n"
        "Send the member's Telegram numeric user ID.\n"
        "(They can get it by messaging @userinfobot)\n\n"
        "(Type /cancel to cancel)"
    )
    return ADDMEMBER_ID


async def addmember_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Please send a numeric Telegram user ID.")
        return ADDMEMBER_ID
    context.user_data["new_member_id"] = target_id
    context.user_data["new_member_teams"] = []

    if target_id in members:
        existing = members[target_id]
        await update.message.reply_text(
            f"👤 Member already exists: *{existing['name']}*\n"
            f"Current teams: {', '.join(existing['teams']) or 'none'}\n\n"
            "Select new teams to assign (or update):",
            parse_mode="Markdown",
            reply_markup=teams_keyboard(existing["teams"], add_done=True)
        )
        context.user_data["new_member_teams"] = list(existing["teams"])
    else:
        members[target_id] = {
            "name":     f"Member #{target_id}",
            "username": str(target_id),
            "teams":    [],
            "chat_id":  target_id,
        }
        await update.message.reply_text(
            "✅ Member pre-registered!\n\n"
            "Now select which teams this member belongs to:",
            reply_markup=teams_keyboard(add_done=True)
        )
    return ADDMEMBER_TEAMS


async def addmember_teams(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "teams_done":
        target_id = context.user_data["new_member_id"]
        selected  = context.user_data["new_member_teams"]
        members[target_id]["teams"] = selected
        team_names = ", ".join(TEAM_DISPLAY.get(t, t) for t in selected) or "No team assigned"
        await query.edit_message_text(
            f"✅ Member registered!\n\n"
            f"👤 ID: {target_id}\n"
            f"👥 Teams: {team_names}\n\n"
            "They will receive all broadcasts. 📢",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    team = data.replace("team_", "")
    selected = context.user_data.get("new_member_teams", [])
    if team in selected:
        selected.remove(team)
    else:
        selected.append(team)
    context.user_data["new_member_teams"] = selected
    await query.edit_message_reply_markup(reply_markup=teams_keyboard(selected, add_done=True))
    return ADDMEMBER_TEAMS


# ── REMOVE MEMBER ──────────────────────────────────────────────

async def removemember_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await admin_only(update, context):
        return ConversationHandler.END
    await update.message.reply_text(
        "🗑️ *Remove a Member*\n\n"
        "Send the Telegram user ID of the member to remove:\n\n"
        "(Type /cancel to cancel)"
    )
    return REMOVEMEMBER_ID


async def removemember_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Please send a numeric Telegram user ID.")
        return REMOVEMEMBER_ID
    if target_id not in members:
        await update.message.reply_text("⚠️ Member not found.")
        return ConversationHandler.END
    name = members[target_id]["name"]
    del members[target_id]
    await update.message.reply_text(f"✅ {name} (ID: {target_id}) has been removed from the fellowship.")
    return ConversationHandler.END


# ── MEMBERS LIST ───────────────────────────────────────────────

async def members_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    if not members:
        await update.message.reply_text("👥 No members registered yet.")
        return
    lines = [f"👥 *FOCUS JIT Members* ({len(members)} total)\n"]
    for uid, m in members.items():
        team_str = ", ".join(m.get("teams", [])) or "No team"
        lines.append(f"• {m['name']} (ID:{uid}) — {team_str}")
    # Split if too long
    full_text = "\n".join(lines)
    if len(full_text) > 4000:
        chunks = [full_text[i:i+4000] for i in range(0, len(full_text), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(full_text, parse_mode="Markdown")


# ── STATS ──────────────────────────────────────────────────────

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_only(update, context):
        return
    lines = [f"📊 *FOCUS JIT Fellowship Statistics*\n", f"👥 Total Members: {len(members)}\n"]
    lines.append("*Members per Team:*")
    for team in ALL_TEAMS:
        count = len(get_team_members(team))
        lines.append(f"  {TEAM_DISPLAY[team]}: {count}")
    lines.append(f"\n📅 Upcoming Events: {len([e for e in events if e['datetime'] > datetime.now()])}")
    lines.append(f"🙏 Active Prayer Requests: {len([r for r in prayer_requests.values() if r.get('active')])}")
    lines.append(f"☕ Charis Posts: {len(charis_posts)}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── SEND VERSE (Bible Study team / Admin only) ─────────────────

async def sendverse_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not (is_admin(uid) or is_bible_study(uid)):
        await update.message.reply_text("⛔ This command is for the Bible Study team or leaders only.")
        return
    await _broadcast_daily_verse(context)
    await update.message.reply_text("✅ Daily verse sent to all members! 📖")


# ─────────────────────────────────────────────────────────────────
#  SCHEDULED JOBS
# ─────────────────────────────────────────────────────────────────

async def _broadcast_daily_verse(context) -> None:
    """
    Scheduled daily verse — sent by Bible Study team to all members at 7:00 AM.
    The sender identity (Bible Study) is intentionally hidden from the message;
    it appears as a FOCUS JIT Fellowship message with no team attribution.
    """
    v = get_verse_of_day()
    text = (
        f"☀️ *Good morning, FOCUS JIT Family!*\n\n"
        f"📖 *Verse of the Day*\n\n"
        f"_{v['verse']}_\n\n"
        f"— *{v['ref']}*\n\n"
        f"✍️ *Morning Reflection:*\n{v['devotional']}\n\n"
        f"Have a blessed and productive day! 🙏✝️\n\n"
        f"_FOCUS JIT — Fellowship of Christian University Students_"
    )
    # Send to all members individually
    for m in get_all_members():
        try:
            await context.bot.send_message(chat_id=m["chat_id"], text=text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Daily verse failed for {m.get('name')}: {e}")
    # Also send to group
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="Markdown")
        logger.info("Daily verse sent to group and all members.")
    except Exception as e:
        logger.error(f"Daily verse group error: {e}")


async def send_daily_verse_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await _broadcast_daily_verse(context)


async def send_weekly_challenge(context: ContextTypes.DEFAULT_TYPE) -> None:
    ch = get_challenge_of_week()
    week = current_week()
    text = (
        f"📚 *New Weekly Bible Challenge!* — Week {week}\n\n"
        f"This week's passage:\n📖 *{ch['passage']}*\n\n"
        f"💭 *Challenge Question:*\n_{ch['question']}_\n\n"
        f"Read the passage, then REPLY to this message with your answer before Sunday.\n"
        f"Everyone who responds earns a streak point! 🔥\n\n"
        f"Let's grow in the Word together! 💪📖"
    )
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="Markdown")
        logger.info("Weekly challenge sent.")
    except Exception as e:
        logger.error(f"Weekly challenge error: {e}")


async def send_weekly_recap(context: ContextTypes.DEFAULT_TYPE) -> None:
    week = current_week()
    responses_this_week = [v for v in challenge_responses.values() if v.get("week") == week]
    if not responses_this_week:
        text = "📊 *Weekly Recap*\n\nNo challenge responses this week — let's do better next Monday! 📖"
    else:
        names = ", ".join(r["name"] for r in responses_this_week)
        text = (
            f"🌟 *Weekly Challenge Recap!*\n\n"
            f"{len(responses_this_week)} member{'s' if len(responses_this_week) > 1 else ''} completed the challenge:\n\n"
            f"👏 {names}\n\n"
            f"Thank you for being in the Word! New challenge comes Monday. 📖\n\n"
            f"Use /leaderboard to see the all-time streaks! 🏆"
        )
    try:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Weekly recap error: {e}")


async def send_event_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now()
    for event in events:
        time_until = event["datetime"] - now
        hours_until = time_until.total_seconds() / 3600
        for target_hours, label in [(24, "tomorrow"), (2, "in 2 hours")]:
            if target_hours - 0.25 < hours_until <= target_hours + 0.25:
                dt_str = event["datetime"].strftime("%A, %B %d at %I:%M %p")
                text = (
                    f"🔔 *Event Reminder!*\n\n"
                    f"📌 *{event['title']}* is happening {label}!\n\n"
                    f"🕒 {dt_str}\n📍 {event['location']}\n"
                    f"{'📝 ' + event['description'] if event.get('description') else ''}\n\n"
                    f"We look forward to seeing you there! 🙌"
                )
                keyboard = [[InlineKeyboardButton("✅ I'll be there!", callback_data=f"rsvp_{event['title'][:20]}")]]
                try:
                    await context.bot.send_message(
                        chat_id=GROUP_CHAT_ID, text=text,
                        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e:
                    logger.error(f"Event reminder error: {e}")


async def rsvp_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("✅ You are registered! See you there. 🙌", show_alert=True)


# ─────────────────────────────────────────────────────────────────
#  CANCEL handler
# ─────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled. What else can I help you with?")
    return ConversationHandler.END


# ─────────────────────────────────────────────────────────────────
#  GROUP CHAT ID DETECTOR
# ─────────────────────────────────────────────────────────────────

async def detect_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type in ["group", "supergroup"]:
        chat_id = update.effective_chat.id
        logger.info(f">>> GROUP CHAT ID: {chat_id} <<<  ← Paste this as GROUP_CHAT_ID in the bot")


# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 55)
    print("  FOCUS JIT Fellowship Bot is starting...")
    print("  Fellowship Of Christian University Students")
    print("=" * 55)

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    async def post_init(application) -> None:
        class Ctx:
            bot = application.bot

        async def daily_verse():   await send_daily_verse_job(Ctx())
        async def weekly_chal():   await send_weekly_challenge(Ctx())
        async def weekly_recap():  await send_weekly_recap(Ctx())
        async def evt_reminders(): await send_event_reminders(Ctx())

        # Daily verse at 7:00 AM every day — managed by Bible Study team
        scheduler.add_job(daily_verse,   CronTrigger(hour=7, minute=0))
        # Weekly challenge every Monday at 8:00 AM
        scheduler.add_job(weekly_chal,   CronTrigger(day_of_week="mon", hour=8, minute=0))
        # Weekly recap every Sunday at 6:00 PM
        scheduler.add_job(weekly_recap,  CronTrigger(day_of_week="sun", hour=18, minute=0))
        # Event reminders every hour
        scheduler.add_job(evt_reminders, CronTrigger(minute=0))
        scheduler.start()
        logger.info("Scheduler started.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ── Conversation: broadcast ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: teamcast ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("teamcast", teamcast_start)],
        states={
            TEAMCAST_TEAM: [CallbackQueryHandler(teamcast_team_selected, pattern=r"^cast_")],
            TEAMCAST_MSG:  [MessageHandler(filters.TEXT & ~filters.COMMAND, teamcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: wednesday ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("wednesday", wednesday_start)],
        states={WEDNESDAY_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, wednesday_send)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: addevent ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addevent", addevent_start)],
        states={ADDEVENT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, addevent_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: addmember ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("addmember", addmember_start)],
        states={
            ADDMEMBER_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, addmember_id)],
            ADDMEMBER_TEAMS: [CallbackQueryHandler(addmember_teams, pattern=r"^(team_|teams_done)")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: removemember ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("removemember", removemember_start)],
        states={REMOVEMEMBER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, removemember_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: pray ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("pray", pray_start)],
        states={PRAY_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, pray_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: prayreply ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("prayreply", prayreply_start)],
        states={PRAYREPLY_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, prayreply_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: charis ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("charis", charis_start)],
        states={CHARIS_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, charis_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Conversation: feedback ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_start)],
        states={FEEDBACK_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # ── Simple commands ──
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("verse",       verse_command))
    app.add_handler(CommandHandler("events",      events_command))
    app.add_handler(CommandHandler("challenge",   challenge_command))
    app.add_handler(CommandHandler("streak",      streak_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("myteams",     myteams_command))
    app.add_handler(CommandHandler("admin",       admin_command))
    app.add_handler(CommandHandler("members",     members_command))
    app.add_handler(CommandHandler("stats",       stats_command))
    app.add_handler(CommandHandler("sendverse",   sendverse_command))

    # ── Button / callback handlers ──
    app.add_handler(CallbackQueryHandler(rsvp_button, pattern=r"^rsvp_"))

    # ── Message handlers ──
    app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUPS, detect_group_id))
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT, respond_to_challenge))

    print("\n✅ Bot is running!")
    print("   Open Telegram, find your bot, and send /start")
    print("   Admin: send /admin to access the leader panel")
    print("   Press Ctrl+C to stop.\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
