# -*- coding: utf-8 -*-
"""蓝色小鲸鱼 · QQ 版（NapCat / OneBot 11）

复用 wpp-bot/bot_api.py 的全部对话逻辑（人格、记忆、群聊节奏、主动消息），
只把「收消息 / 发消息 / 图片识别」这三层换成 OneBot 11。

  · 收：连 NapCat 正向 WS（ws://127.0.0.1:3001），收 message 事件
  · 发：调 NapCat HTTP（http://127.0.0.1:3000）send_private_msg / send_group_msg
"""

import base64
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.expanduser("~/shared-memory"))

import bot_api as core          # noqa: E402
from bot_api import log         # noqa: E402

CFG = core.CFG
ONE = CFG.get("onebot") or {}
OB_HTTP = str(ONE.get("http", "http://127.0.0.1:3000")).rstrip("/")
OB_WS = str(ONE.get("ws", "ws://127.0.0.1:3001"))
OB_TOKEN = str(ONE.get("token", "") or "")
TIMEOUT = float(ONE.get("timeout", 40) or 40)

SELF_ID = int(CFG.get("self_id") or 0)
GROUP_WHITELIST = {int(x) for x in ((CFG.get("group") or {}).get("whitelist") or [])
                   if str(x).strip()}
PRO = CFG.get("proactive") or {}
TARGET = int(PRO.get("target") or 0)
OWNER_IDS = {int(x) for x in (CFG.get("owners") or []) if str(x).strip()}

# 让 core 的逻辑认识 QQ 号（它原本认 wxid）
core.PROACTIVE_TARGET_WXID = ("u%d" % TARGET) if TARGET else ""
core.PROACTIVE_ENABLED = bool(PRO.get("enabled", False))
core.OWNER_WXIDS = {"u%d" % i for i in OWNER_IDS}
core.PERSONA = core.PERSONA.replace("微信", "QQ")

_SEEN = set()
_SEEN_ORDER = []


# ------------------------------------------------------------------ OneBot API
def ob(action, params=None, timeout=None):
    body = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if OB_TOKEN:
        headers["Authorization"] = "Bearer " + OB_TOKEN
    req = urllib.request.Request(OB_HTTP + "/" + action, data=body,
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout or TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _ok(res):
    return isinstance(res, dict) and (res.get("status") == "ok"
                                      or res.get("retcode") == 0)


def send_text(to, content, at=None):
    to = str(to or "")
    segs = []
    if at:
        segs.append({"type": "at", "data": {"qq": str(at)}})
    if content:
        segs.append({"type": "text", "data": {"text": content}})
    if not segs:
        return False
    try:
        if to.startswith("g"):
            res = ob("send_group_msg", {"group_id": int(to[1:]), "message": segs})
        else:
            res = ob("send_private_msg",
                     {"user_id": int(to.lstrip("u")), "message": segs})
    except Exception:
        log.warning("发送失败(%s)", to, exc_info=True)
        return False
    if not _ok(res):
        log.warning("发送失败(%s): %s", to,
                    res.get("message") or res.get("wording") or res)
    return _ok(res)


def send_voice(to, content):
    """QQ 端暂不发语音条（silk 编码还没接），一律退回文字。"""
    return False


def describe_image_url(url):
    """OneBot 图片给的是 url，下载后走和微信版一样的识图。"""
    if not (url and core.IMAGE_DESC):
        return ""
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            raw = r.read()
    except Exception:
        log.warning("图片下载失败", exc_info=True)
        return ""
    if not raw:
        return ""
    b64 = base64.b64encode(raw).decode("ascii")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": core.VISION_PROMPT},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + b64,
            "detail": core.VISION_DETAIL,
        }},
    ]}]
    try:
        out = core.deepseek(messages, max_tokens=core.VISION_MAX_TOKENS,
                            temperature=0.2, model=core.VISION_MODEL,
                            extra={"thinking": {"type": "disabled"}})
    except Exception:
        log.warning("识图请求失败", exc_info=True)
        return ""
    return (out or "").strip().strip('"“”')[:300]


def resolve_media(raw, placeholder):
    kind = str((raw or {}).get("kind") or "")
    if kind == "image" and core.IMAGE_DESC:
        desc = describe_image_url((raw or {}).get("url"))
        if desc:
            return "[发来一张图片，画面是：%s]" % desc
    return placeholder


# ------------------------------------------------------------------ 记忆来源
def spawn_extract(who, name, texts, reply):
    if not (core.MEMORY_ON and core.MEMORY_EXTRACT):
        return
    joined = "\n".join(texts)
    if len(joined) + len(reply) < 12:
        return
    try:
        threading.Thread(
            target=core.memlib.extract,
            args=(core.deepseek, joined, reply),
            kwargs={"source": "qq",
                    "scope": "owner" if core.is_owner(who, name) else "public",
                    "logger": log},
            daemon=True).start()
    except Exception:
        log.warning("[记忆] 起线程失败", exc_info=True)


# 把 core 里那三层换成 QQ 的实现
core.send_text = send_text
core.send_voice = send_voice
core.resolve_media = resolve_media
core.spawn_extract = spawn_extract


# ------------------------------------------------------------------ 收消息
def _segments(ev):
    segs = ev.get("message")
    if isinstance(segs, str):
        return [{"type": "text", "data": {"text": segs}}]
    return segs or []


def handle(ev):
    try:
        if ev.get("post_type") != "message":
            return
        mt = ev.get("message_type")
        if mt not in ("private", "group"):
            return
        self_id = int(ev.get("self_id") or SELF_ID or 0)
        uid = int(ev.get("user_id") or 0)
        if not uid or uid == self_id:
            return

        mid = ev.get("message_id")
        with core.lock:
            if mid in _SEEN:
                return
            _SEEN.add(mid)
            _SEEN_ORDER.append(mid)
            if len(_SEEN_ORDER) > 5000:
                for k in _SEEN_ORDER[:2000]:
                    _SEEN.discard(k)
                del _SEEN_ORDER[:2000]

        at_me = False
        media = None
        parts = []
        for s in _segments(ev):
            t = s.get("type")
            d = s.get("data") or {}
            if t == "text":
                parts.append(str(d.get("text") or ""))
            elif t == "at":
                qq = str(d.get("qq") or "")
                if qq == str(self_id):
                    at_me = True
                elif qq:
                    parts.append("@" + str(d.get("name") or qq))
            elif t == "image":
                parts.append("[发来一张图片]")
                media = {"kind": "image",
                         "url": d.get("url") or d.get("file") or ""}
            elif t == "record":
                parts.append("[发来一条语音]")
                media = {"kind": "voice", "url": d.get("url") or ""}
            elif t in ("mface", "face"):
                parts.append("[发来一个表情]")
            elif t == "file":
                parts.append("[发来一个文件]")
            elif t == "reply":
                pass
        text = " ".join(p for p in parts if p).strip()

        sender = ev.get("sender") or {}
        name = str(sender.get("card") or sender.get("nickname") or uid)
        now = time.time()

        if mt == "group":
            gid = int(ev.get("group_id") or 0)
            if not gid or not core.GROUP_ENABLED:
                return
            # 群聊白名单：空 = 一个群都不说话
            if gid not in GROUP_WHITELIST:
                log.info("[群 %s] 不在白名单，忽略", gid)
                return
            if not text and not media:
                return
            core.last_user_time["g%d" % gid] = now
            core.on_group("g%d" % gid, name, text, at_me)
        else:
            who = "u%d" % uid
            if not text and not media:
                return
            core.last_user_time[who] = now
            core.on_private(who, name, text, media)
    except Exception:
        log.exception("处理消息出错")


# ------------------------------------------------------------------ 主循环
def ws_loop():
    from websockets.sync.client import connect

    url = OB_WS
    if OB_TOKEN:
        url += ("&" if "?" in url else "?") + "access_token=" + urllib.parse.quote(OB_TOKEN)
    core.START_TS = time.time()
    log.info("连接 NapCat OneBot：%s", OB_WS)
    while True:
        try:
            with connect(url, ping_interval=20, max_size=32 * 1024 * 1024,
                         open_timeout=20) as ws:
                log.info("OneBot 已连接，开始收消息")
                while True:
                    try:
                        raw = ws.recv(timeout=120)
                    except TimeoutError:
                        continue
                    try:
                        ev = json.loads(raw)
                    except Exception:
                        continue
                    handle(ev)
        except Exception as exc:
            log.warning("OneBot 断开：%s，5 秒后重连", exc)
            time.sleep(5)


def main():
    log.info("蓝色小鲸鱼（QQ 版）启动 self=%s owner=%s", SELF_ID, sorted(OWNER_IDS))
    try:
        info = ob("get_login_info", {})
        log.info("登录账号：%s", (info.get("data") or info))
    except Exception as exc:
        log.warning("查登录信息失败（可能还没登录）：%s", exc)
    if core.MEMORY_ON:
        try:
            st = core.memlib.stats()
            log.info("[记忆] 共享库 %d 条，来源 %s", st["total"], st["by_source"])
        except Exception:
            pass
    if core.PROACTIVE_ENABLED and core.PROACTIVE_TARGET_WXID:
        threading.Thread(target=core.proactive_loop, daemon=True).start()
    if core.MEMORY_ON:
        threading.Thread(target=core.memory_maint_loop, daemon=True).start()
    ws_loop()


if __name__ == "__main__":
    main()
