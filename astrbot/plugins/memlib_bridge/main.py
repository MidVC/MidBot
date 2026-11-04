import json
import os
import re
import sys
import threading
import urllib.request

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star

sys.path.insert(0, os.path.expanduser("~/shared-memory"))
try:
    import memlib
except Exception:  # pragma: no cover
    memlib = None

BASE = os.path.dirname(os.path.abspath(__file__))
IDENTITIES_PATH = os.path.join(BASE, "identities.json")
CFG_PATH = os.path.expanduser("~/astrbot/data/cmd_config.json")

DEFAULT_IDENTITIES = {
    "owner_address": "爸爸",
    "default_relation": "stranger",
    "users": {},
}

FAMILY_WORDS = ("老爸", "爸爸")


def load_identities() -> dict:
    data = json.loads(json.dumps(DEFAULT_IDENTITIES))
    try:
        with open(IDENTITIES_PATH, encoding="utf-8") as fh:
            user = json.load(fh)
    except Exception:
        return data
    for k in ("owner_address", "default_relation"):
        if user.get(k):
            data[k] = str(user[k])
    if isinstance(user.get("users"), dict):
        data["users"] = {str(k): v for k, v in user["users"].items()}
    # 兼容旧格式 {"owner": {"qq": [...], "discord": [...]}}
    if isinstance(user.get("owner"), dict):
        for plat, ids in user["owner"].items():
            for i in ids or []:
                data["users"].setdefault(f"{plat}:{i}", {"name": "MidC", "relation": "owner"})
    return data


def platform_key(event: AstrMessageEvent) -> str:
    name = (event.get_platform_name() or "").lower()
    if "discord" in name:
        return "discord"
    if "aiocqhttp" in name or "qq" in name:
        return "qq"
    return name or "unknown"


def resolve(event: AstrMessageEvent, identities: dict):
    plat = platform_key(event)
    sid = str(event.get_sender_id() or "")
    entry = (identities.get("users") or {}).get(f"{plat}:{sid}") or {}
    rel = str(entry.get("relation") or identities.get("default_relation") or "stranger")
    name = str(entry.get("name") or event.get_sender_name() or sid)
    return plat, sid, name, rel, rel == "owner"


def scrub_family(text: str, replacement: str = "你") -> str:
    for w in FAMILY_WORDS:
        text = text.replace(w, replacement)
    return text


def scrub_contexts(contexts, replacement="你"):
    """把历史里已经叫出口的「老爸/爸爸」改写掉，避免模型模仿自己。"""
    changed = 0
    for m in contexts or []:
        if m.get("role") != "assistant":
            continue
        content = m.get("content")
        if isinstance(content, str):
            new = scrub_family(content, replacement)
            if new != content:
                m["content"] = new
                changed += 1
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    new = scrub_family(part["text"], replacement)
                    if new != part["text"]:
                        part["text"] = new
                        changed += 1
    return changed


def _provider_conf():
    key = base = model = ""
    try:
        with open(CFG_PATH, encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
        sources = {s.get("id"): s for s in (cfg.get("provider_sources") or [])}
        for p in cfg.get("provider") or []:
            src = sources.get(p.get("provider_source_id")) or {}
            if p.get("id") != "deepseek" and src.get("id") != "deepseek":
                continue
            keys = src.get("key") or []
            if isinstance(keys, str):
                keys = [keys]
            key = keys[0] if keys else ""
            if isinstance(key, str) and key.startswith("$"):
                key = os.environ.get(key[1:], "")
            base = src.get("api_base") or ""
            model = p.get("model") or ""
            break
    except Exception:
        pass
    return key, base or "https://api.deepseek.com/v1", model or "deepseek-chat"


def _llm(messages, max_tokens=300, temperature=0.2):
    key, base, model = _provider_conf()
    if not key:
        raise RuntimeError("no api key found for deepseek provider")
    body = json.dumps(
        {"model": model, "messages": messages, "max_tokens": max_tokens,
         "temperature": temperature, "stream": False},
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())
    return (data["choices"][0]["message"]["content"] or "").strip()


class MemlibBridge(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._user_text = {}
        self._guest = {}
        self._owner = {}

    @filter.on_llm_request(priority=-100)
    async def inject(self, event: AstrMessageEvent, req: ProviderRequest):
        self._user_text[event.unified_msg_origin] = event.message_str
        identities = load_identities()
        plat, sid, name, rel, owner = resolve(event, identities)
        address = identities.get("owner_address", "爸爸")
        self._guest[event.unified_msg_origin] = (not owner)
        self._owner[event.unified_msg_origin] = owner

        if owner:
            rule = (
                f"【当前说话的人】{name}（{plat}:{sid}），关系：{address}本人。"
                f"可以自然地叫{address}。"
            )
        else:
            rule = (
                f"【当前说话的人】{name}（{plat}:{sid}），关系：{rel}，**不是**{address}。\n"
                f"绝对不要用「{address}」「老爸」称呼他，也不要撒娇或说父女之间的话；"
                "就当普通朋友，用「你」或对方名字称呼。"
            )

        # 1) 系统提示末尾（优先级最高）
        req.system_prompt = (req.system_prompt or "").rstrip() + "\n\n" + rule

        # 2) 当前这轮用户消息前面贴一个紧凑标签（模型对最近输入最敏感）
        tag = (
            f"[speaker] {name} | {plat}:{sid} | relation={rel}"
            + ("" if owner else " | never call this person 爸爸/老爸")
        )
        req.prompt = tag + "\n" + (req.prompt or "")

        # 3) 历史里已经叫错的，改写掉，别让它继续模仿自己
        if not owner:
            fixed = scrub_contexts(req.contexts, "你")
            if fixed:
                logger.info("[memlib_bridge] scrubbed %s family references in history", fixed)

        logger.info("[memlib_bridge] %s:%s (%s) -> %s", plat, sid, name,
                    "owner" if owner else "guest")

        if memlib and owner:
            try:
                block = memlib.render(view="owner", limit=40, width=2000)
                if block:
                    req.system_prompt += (
                        "\n\n【你记得的事】\n" + block
                        + "\n（这些是你长期记住的，自然地用，别一口气全说出来。）"
                    )
            except Exception:
                logger.exception("[memlib_bridge] 注入记忆失败")

    @filter.on_llm_response()
    async def collect(self, event: AstrMessageEvent, resp: LLMResponse):
        reply = (getattr(resp, "completion_text", "") or "").strip()
        if reply and self._guest.pop(event.unified_msg_origin, False):
            cleaned = scrub_family(reply, "你")
            if cleaned != reply:
                logger.info("[memlib_bridge] output scrubbed: %s", cleaned[:80])
                resp.completion_text = cleaned
        if not memlib:
            return
        if not self._owner.pop(event.unified_msg_origin, False):
            self._user_text.pop(event.unified_msg_origin, None)
            return
        user = self._user_text.pop(event.unified_msg_origin, "")
        if not reply or not user or len(user) + len(reply) < 12:
            return
        try:
            threading.Thread(
                target=memlib.extract,
                args=(_llm, user, reply),
                kwargs={"source": "astrbot", "scope": "owner", "logger": logger},
                daemon=True,
            ).start()
        except Exception:
            logger.exception("[memlib_bridge] 起线程失败")
