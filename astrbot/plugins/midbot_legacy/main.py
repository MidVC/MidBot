# -*- coding: utf-8 -*-
"""旧 MidBot（discord.py, ~/projects/MidBot）迁移到 AstrBot 的插件。

搬过来的东西：
  /ping               -> Hellosu!
  /roll [n]           -> 1..n 随机
  /mirror [方向]      -> 把同一张消息里的图片镜像（left/right/top/bottom，支持 gif）
  含 "ciallo"         -> Ciallo～(∠・ω< )⌒★
  >rs <osu 用户名>    -> 最近一个成绩（ossapi）
  每天 02:04          -> 给固定用户/频道发 "Time"

没有搬：/sync、/cmd（AstrBot 自己管斜杠指令）、MySQL 那套（旧代码里没在用）。
"""

import asyncio
import io
import json
import os
import random
import re
import time
from datetime import datetime, timedelta

from PIL import Image as PILImage
from PIL import ImageSequence

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image
from astrbot.api.star import Context, Star

BASE = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(BASE, "config.json")
ENV_PATH = os.path.expanduser("~/projects/MidBot/MidBot/.env.midc")
ASTRBOT_CONF = os.path.expanduser("~/astrbot/data/cmd_config.json")

DEFAULTS = {
    "time_task": {
        "enable": True,
        "hour": 2,
        "minute": 4,
        "users": [],
        "channels": [],
        "message": "Time",
    }
}


def load_conf():
    conf = json.loads(json.dumps(DEFAULTS))
    try:
        with open(CONF_PATH, encoding="utf-8") as fh:
            user = json.load(fh)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(conf.get(k), dict):
                conf[k].update(v)
            else:
                conf[k] = v
    except Exception:
        pass
    return conf


def load_env():
    env = {}
    try:
        with open(ENV_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


# ---------------------------------------------------------------- osu
def handle_rs(user_name: str) -> str:
    env = load_env()
    cid = env.get("OAUTHCLIENTID") or os.environ.get("OAUTHCLIENTID")
    csec = env.get("OAUTHCLIENTSECRET") or os.environ.get("OAUTHCLIENTSECRET")
    if not cid or not csec:
        return "osu API 没配置（OAUTHCLIENTID / OAUTHCLIENTSECRET）"
    try:
        from ossapi import Ossapi
        api = Ossapi(int(cid), csec)
    except Exception as exc:
        return f"osu API 初始化失败：{exc}"
    try:
        user_id = api.user(user=user_name).id
    except Exception:
        return f"User {user_name} not found!"
    try:
        scores = api.user_scores(user_id, "recent", include_fails=True,
                                 mode="osu", limit=10, offset=0)
    except Exception as exc:
        return f"查成绩失败：{exc}"
    if not scores:
        return f"User {user_name} does not have a recent play on bancho!"
    s = scores[0]
    pp = "None pp" if s.pp is None else f"{s.pp:.2f}pp"
    out = (f"{pp} on {s.beatmapset.title} +{s.mods}, "
           f"{s.accuracy * 100:.2f}%, {s.max_combo}x")
    derankers = tuple(int(x) for x in (load_conf().get("deranker_ids") or []))
    if user_id in derankers:
        out += "\nderanker!"
    return out


# ---------------------------------------------------------------- 镜像
def _flip(img: PILImage.Image, direction: str) -> PILImage.Image:
    w, h = img.size
    canvas = PILImage.new(img.mode, (max(w - 1, 1), max(h - 1, 1)))
    if direction == "right":
        half = img.crop((w // 2, 0, w, h))
        canvas.paste(half.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT), (0, 0))
        canvas.paste(half, (w // 2, 0))
    elif direction == "top":
        half = img.crop((0, 0, w, h // 2))
        canvas.paste(half, (0, 0))
        canvas.paste(half.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM), (0, h // 2))
    elif direction == "bottom":
        half = img.crop((0, h // 2, w, h))
        canvas.paste(half.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM), (0, 0))
        canvas.paste(half, (0, h // 2))
    else:
        half = img.crop((0, 0, w // 2, h))
        canvas.paste(half, (0, 0))
        canvas.paste(half.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT), (w // 2, 0))
    return canvas


def mirror_file(src: str, direction: str) -> str:
    img = PILImage.open(src)
    out_dir = os.path.join(BASE, "tmp")
    os.makedirs(out_dir, exist_ok=True)
    name = f"mirror-{int(time.time())}"
    if getattr(img, "is_animated", False):
        frames = []
        for frame in ImageSequence.Iterator(img):
            frames.append(_flip(frame.convert("RGBA"), direction))
        out = os.path.join(out_dir, name + ".gif")
        frames[0].save(out, format="GIF", save_all=True,
                       append_images=frames[1:], loop=0)
    else:
        out = os.path.join(out_dir, name + ".png")
        _flip(img.convert("RGBA"), direction).save(out)
    return out


# ---------------------------------------------------------------- Discord 直发
def discord_token() -> str:
    try:
        with open(ASTRBOT_CONF, encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
        for p in cfg.get("platform") or []:
            if p.get("type") == "discord":
                return str(p.get("discord_token") or "")
    except Exception:
        pass
    return ""


async def discord_send(channel_id: int, content: str) -> None:
    import aiohttp
    token = discord_token()
    if not token:
        logger.warning("[midbot] 没有 discord token，发不了定时消息")
        return
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url, json={"content": content}, headers=headers) as r:
            if r.status >= 300:
                logger.warning("[midbot] 定时消息失败 %s: %s", r.status, await r.text())


class MidBotLegacy(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.conf = load_conf()
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._time_loop())
        except Exception:
            logger.warning("[midbot] 定时任务没起来", exc_info=True)

    # ---------------- 指令
    @filter.command("ping")
    async def ping(self, event: AstrMessageEvent):
        """Hellosu!"""
        event.stop_event()
        yield event.plain_result("Hellosu!")

    @filter.command("roll")
    async def roll(self, event: AstrMessageEvent):
        """roll 一个数，默认 1-100"""
        event.stop_event()
        parts = (event.message_str or "").split()
        n = 100
        if len(parts) > 1:
            try:
                n = int(parts[1])
            except ValueError:
                n = 100
        if n <= 0:
            yield event.plain_result(f"Wdym roll {n} ?!")
            return
        yield event.plain_result(str(random.randint(1, n)))

    @filter.command("mirror")
    async def mirror(self, event: AstrMessageEvent):
        """把消息里的图片镜像，方向：left/right/top/bottom"""
        event.stop_event()
        parts = (event.message_str or "").split()
        direction = parts[1].lower() if len(parts) > 1 else "left"
        if direction not in ("left", "right", "top", "bottom"):
            direction = "left"
        imgs = [c for c in event.message_obj.message if isinstance(c, Image)]
        if not imgs:
            yield event.plain_result("附一张 jpg/png/gif 再 /mirror 一下")
            return
        try:
            src = await imgs[0].convert_to_file_path()
            out = await asyncio.to_thread(mirror_file, src, direction)
            yield event.plain_result(f"Mirrored respective to the {direction} half!")
            yield event.image_result(out)
        except Exception:
            logger.exception("[midbot] 镜像失败")
            yield event.plain_result("failed")

    # ---------------- 彩蛋 / >rs
    @filter.event_message_type(filter.EventMessageType.ALL, priority=1000)
    async def legacy_text(self, event: AstrMessageEvent):
        text = event.message_str or ""
        low = text.lower().strip()
        if "ciallo" in low:
            event.stop_event()
            yield event.plain_result("Ciallo～(∠・ω< )⌒★")
            return
        if low.startswith(">rs"):
            event.stop_event()
            parts = text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                yield event.plain_result("用法：>rs <osu 用户名>")
                return
            name = parts[1].strip()
            out = await asyncio.to_thread(handle_rs, name)
            yield event.plain_result(out)

    # ---------------- 每日 Time
    async def _time_loop(self):
        conf = self.conf.get("time_task") or {}
        if not conf.get("enable", True):
            return
        hour, minute = int(conf.get("hour", 2)), int(conf.get("minute", 4))
        msg = str(conf.get("message", "Time"))
        while True:
            try:
                now = datetime.now()
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                await asyncio.sleep((target - now).total_seconds())
                for cid in (conf.get("channels") or []):
                    await discord_send(int(cid), msg)
                logger.info("[midbot] 每日 %02d:%02d 消息已发", hour, minute)
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("[midbot] 定时任务出错")
                await asyncio.sleep(60)
