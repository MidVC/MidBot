import json
import os
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
    "owner": {"qq": [], "discord": []},
    "owner_address": "爸爸",
}


def load_identities() -> dict:
    data = json.loads(json.dumps(DEFAULT_IDENTITIES))
    try:
        with open(IDENTITIES_PATH, encoding="utf-8") as fh:
            user = json.load(fh)
        if isinstance(user.get("owner"), dict):
            data["owner"].update(user["owner"])
        if user.get("owner_address"):
            data["owner_address"] = str(user["owner_address"])
    except Exception:
        pass
    return data


def platform_key(event: AstrMessageEvent) -> str:
    name = (event.get_platform_name() or "").lower()
    if "discord" in name:
        return "discord"
    if "aiocqhttp" in name or "qq" in name:
        return "qq"
    return name or "unknown"


def is_owner(event: AstrMessageEvent, identities: dict) -> bool:
    ids = identities.get("owner", {}).get(platform_key(event), []) or []
    return str(event.get_sender_id() or "") in {str(x) for x in ids}


def _provider_conf():
    """返回 (api_key, api_base, model)。兼容 AstrBot 新的 provider_sources 结构。"""
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

    @filter.on_llm_request(priority=-100)
    async def inject(self, event: AstrMessageEvent, req: ProviderRequest):
        self._user_text[event.unified_msg_origin] = event.message_str
        identities = load_identities()
        plat = platform_key(event)
        sid = str(event.get_sender_id() or "")
        name = str(event.get_sender_name() or sid)
        owner = is_owner(event, identities)
        self._guest[event.unified_msg_origin] = (not owner)
        address = identities.get("owner_address", "爸爸")

        if owner:
            who = (
                f"【当前对话者】是{address}本人（{plat}，ID {sid}）。"
                f"可以自然地叫{address}。"
            )
        else:
            who = (
                f"【当前对话者】是「{name}」（{plat}，ID {sid}），不是{address}。\n"
                f"这条优先于上面所有人格设定：绝对不要用「{address}」「老爸」或任何亲属称呼叫他，"
                "也不要撒娇、不要说只有父女之间才说的话。就当普通朋友，称呼用「你」或者对方的名字。"
            )

        # 身份说明放在最后，优先级最高
        req.system_prompt = (req.system_prompt or "").rstrip() + "\n\n" + who
        logger.info("[memlib_bridge] %s %s -> %s", plat, sid, "owner" if owner else "guest")

        if not memlib:
            return
        try:
            block = memlib.render(view="owner" if owner else "public", limit=40, width=2000)
            if block and owner:
                req.system_prompt += (
                    "\n\n【你记得的事】\n" + block
                    + "\n（这些是你长期记住的，自然地用，别一口气全说出来。）"
                )
        except Exception:
            logger.exception("[memlib_bridge] 注入记忆失败")

    @filter.on_llm_response()
    async def collect(self, event: AstrMessageEvent, resp: LLMResponse):
        if not memlib:
            return
        reply = (getattr(resp, "completion_text", "") or "").strip()
        if self._guest.pop(event.unified_msg_origin, False) and reply:
            for word in ("老爸", "爸爸"):
                reply = reply.replace(word, "你")
            if getattr(resp, "completion_text", None):
                resp.completion_text = reply
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
