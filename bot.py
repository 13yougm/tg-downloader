from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from redis.asyncio import Redis

from .config import settings
from .jobs import JobStore, PendingStore
from .models import DownloadJob
from .monetization import user_plan
from .queue import RedisQueue
from .security import detect_platform, extract_first_url, validate_url
from .storage import RedisStorage, UserPrefs
from .utils import now_ts, setup_logging


log = logging.getLogger(__name__)
router = Router()


def kb_choose_format(pending_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🎥 Video HD", callback_data=f"dl:{pending_id}:video:hd")
    b.button(text="🎥 Video SD", callback_data=f"dl:{pending_id}:video:sd")
    b.button(text="🎵 Audio M4A", callback_data=f"dl:{pending_id}:audio:m4a")
    b.button(text="🎵 Audio MP3", callback_data=f"dl:{pending_id}:audio:mp3")
    b.adjust(2, 2)
    return b.as_markup()


def kb_settings(prefs: UserPrefs) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"Default video: {'HD' if prefs.default_video_quality=='hd' else 'SD'}", callback_data="set:video")
    b.button(text=f"Default audio: {prefs.default_audio_fmt.upper()}", callback_data="set:audio")
    b.button(text=f"Mode: {prefs.auto_mode}", callback_data="set:mode")
    b.adjust(1)
    return b.as_markup()


def kb_settings_video() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="HD", callback_data="set:video:hd")
    b.button(text="SD", callback_data="set:video:sd")
    b.button(text="⬅ Back", callback_data="set:back")
    b.adjust(2, 1)
    return b.as_markup()


def kb_settings_audio() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="M4A", callback_data="set:audio:m4a")
    b.button(text="MP3", callback_data="set:audio:mp3")
    b.button(text="⬅ Back", callback_data="set:back")
    b.adjust(2, 1)
    return b.as_markup()


def kb_settings_mode(prefs: UserPrefs) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for mode in ("ask", "audio", "video"):
        mark = "✓ " if prefs.auto_mode == mode else ""
        b.button(text=f"{mark}{mode}", callback_data=f"set:mode:{mode}")
    b.button(text="⬅ Back", callback_data="set:back")
    b.adjust(3, 1)
    return b.as_markup()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Надішли посилання на відео/рілс/шортс.

"
        "• 1 посилання = 1 дія
"
        "• /settings — дефолтна якість
"
        "• /audio — тільки музика
"
        "• /video — тільки відео
"
        "• /status — черга",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Підтримка: YouTube, TikTok, Instagram, Facebook, Douyin, Kuaishou та будь-які сайти з yt-dlp.
"
        "Формати: Video (HD/SD), Audio (M4A/MP3).
"
        "Ліміт: 2 ГБ.",
    )


@router.message(Command("audio"))
async def cmd_audio(message: Message, storage: RedisStorage) -> None:
    prefs = await storage.get_prefs(message.from_user.id)
    prefs.auto_mode = "audio"
    await storage.set_prefs(message.from_user.id, prefs)
    await message.answer("Режим: тільки аудіо. Надішли посилання.")


@router.message(Command("video"))
async def cmd_video(message: Message, storage: RedisStorage) -> None:
    prefs = await storage.get_prefs(message.from_user.id)
    prefs.auto_mode = "video"
    await storage.set_prefs(message.from_user.id, prefs)
    await message.answer("Режим: тільки відео. Надішли посилання.")


@router.message(Command("settings"))
async def cmd_settings(message: Message, storage: RedisStorage) -> None:
    prefs = await storage.get_prefs(message.from_user.id)
    await message.answer("Налаштування", reply_markup=kb_settings(prefs))


@router.callback_query(F.data.startswith("set:"))
async def cb_settings(call: CallbackQuery, storage: RedisStorage) -> None:
    parts = (call.data or "").split(":")
    prefs = await storage.get_prefs(call.from_user.id)

    if parts == ["set", "back"]:
        await call.message.edit_text("Налаштування", reply_markup=kb_settings(prefs))
        await call.answer()
        return

    if parts == ["set", "video"]:
        await call.message.edit_text("Default video quality", reply_markup=kb_settings_video())
        await call.answer()
        return

    if parts == ["set", "audio"]:
        await call.message.edit_text("Default audio format", reply_markup=kb_settings_audio())
        await call.answer()
        return

    if parts == ["set", "mode"]:
        await call.message.edit_text("Mode (link → action)", reply_markup=kb_settings_mode(prefs))
        await call.answer()
        return

    if len(parts) == 3 and parts[0] == "set" and parts[1] == "video" and parts[2] in {"hd", "sd"}:
        prefs.default_video_quality = parts[2]
        await storage.set_prefs(call.from_user.id, prefs)
        await call.message.edit_text("Збережено", reply_markup=kb_settings(prefs))
        await call.answer()
        return

    if len(parts) == 3 and parts[0] == "set" and parts[1] == "audio" and parts[2] in {"mp3", "m4a"}:
        prefs.default_audio_fmt = parts[2]
        await storage.set_prefs(call.from_user.id, prefs)
        await call.message.edit_text("Збережено", reply_markup=kb_settings(prefs))
        await call.answer()
        return

    if len(parts) == 3 and parts[0] == "set" and parts[1] == "mode" and parts[2] in {"ask", "audio", "video"}:
        prefs.auto_mode = parts[2]
        await storage.set_prefs(call.from_user.id, prefs)
        await call.message.edit_text("Збережено", reply_markup=kb_settings(prefs))
        await call.answer()
        return

    await call.answer("Unknown", show_alert=False)


@router.message(Command("status"))
async def cmd_status(message: Message, queue: RedisQueue) -> None:
    p, n = await queue.length()
    await message.answer(f"Queue: premium={p}, normal={n}")


@router.message(F.text)
async def on_text(message: Message, redis: Redis, queue: RedisQueue, storage: RedisStorage) -> None:
    if not message.from_user:
        return

    url = extract_first_url(message.text or "")
    if not url:
        return

    # Security: SSRF guard
    check = await validate_url(url)
    if not check.ok:
        await message.reply("Некоректне посилання.")
        return

    plan = user_plan(message.from_user.id)
    if not plan.unlimited:
        allowed, _remaining = await storage.touch_rate_limit(message.from_user.id, settings.free_requests_per_hour)
        if not allowed:
            await message.reply("Ліміт запитів вичерпано. Спробуй пізніше або premium.")
            return

    prefs = await storage.get_prefs(message.from_user.id)
    platform = detect_platform(url)

    # If mode is forced -> enqueue immediately
    if prefs.auto_mode in {"audio", "video"}:
        kind = prefs.auto_mode
        quality = prefs.default_video_quality
        audio_fmt = prefs.default_audio_fmt
        await enqueue_job(
            message=message,
            redis=redis,
            queue=queue,
            storage=storage,
            url=url,
            kind=kind,
            quality=quality,
            audio_fmt=audio_fmt,
        )
        return

    # Ask via inline keyboard
    pending = PendingStore(redis)
    pending_id = JobStore(redis).new_id()[:16]
    await pending.put(pending_id, url, ttl_sec=900)

    await message.reply(
        f"{platform} • вибери формат",
        reply_markup=kb_choose_format(pending_id),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data.startswith("dl:"))
async def cb_download(call: CallbackQuery, redis: Redis, queue: RedisQueue, storage: RedisStorage) -> None:
    if not call.message or not call.from_user:
        await call.answer()
        return

    parts = (call.data or "").split(":")
    # dl:<pending_id>:<kind>:<q_or_fmt>
    if len(parts) != 4:
        await call.answer("Bad", show_alert=False)
        return

    _dl, pending_id, kind, q = parts

    pending = PendingStore(redis)
    url = await pending.pop(pending_id)
    if not url:
        await call.answer("Лінк протух. Надішли ще раз.", show_alert=True)
        return

    if kind == "video":
        quality = q if q in {"hd", "sd"} else "hd"
        prefs = await storage.get_prefs(call.from_user.id)
        audio_fmt = prefs.default_audio_fmt
    else:
        quality = "hd"
        audio_fmt = q if q in {"mp3", "m4a"} else "m4a"

    await call.message.edit_text("В черзі…")
    await call.answer()

    # enqueue
    fake_message = call.message
    await enqueue_job(
        message=fake_message,
        redis=redis,
        queue=queue,
        storage=storage,
        url=url,
        kind=kind,
        quality=quality,
        audio_fmt=audio_fmt,
        user_id=call.from_user.id,
    )


async def enqueue_job(
    *,
    message: Message,
    redis: Redis,
    queue: RedisQueue,
    storage: RedisStorage,
    url: str,
    kind: str,
    quality: str,
    audio_fmt: str,
    user_id: int | None = None,
) -> None:
    if not message.chat:
        return

    uid = user_id if user_id is not None else (message.from_user.id if message.from_user else 0)
    plan = user_plan(uid)

    job_store = JobStore(redis)
    job_id = job_store.new_id()

    job = DownloadJob(
        job_id=job_id,
        user_id=uid,
        chat_id=message.chat.id,
        reply_to_message_id=message.message_id,
        url=url,
        kind=kind,
        quality=quality,
        audio_fmt=audio_fmt,
        created_at=now_ts(),
    )

    await job_store.put(job, status="queued")
    await storage.add_user_job(uid, job_id)

    await queue.enqueue(job, priority=plan.priority_queue)

    await message.answer(
        f"Queued: {kind.upper()} {quality.upper() if kind=='video' else audio_fmt.upper()}
"
        f"ID: {job_id[:8]}",
        disable_web_page_preview=True,
    )


async def _build_dp() -> tuple[Dispatcher, Redis, RedisQueue, RedisStorage]:
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    queue = RedisQueue(redis)
    storage = RedisStorage(redis)

    dp = Dispatcher()
    dp.include_router(router)

    # Inject deps via context
    dp["redis"] = redis
    dp["queue"] = queue
    dp["storage"] = storage

    return dp, redis, queue, storage


async def main() -> None:
    setup_logging(settings.log_level)
    bot = Bot(settings.bot_token, parse_mode=ParseMode.HTML)

    dp, redis, _queue, _storage = await _build_dp()

    try:
        await dp.start_polling(bot)
    finally:
        await redis.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
