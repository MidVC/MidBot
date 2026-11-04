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
    try:
        with open(CFG_PATH, encoding="utf-8-sig") as fh:
            cfg = json.load(fh)
        for p in cfg.get("provider") or []:
            if p.get("id") == "deepseek":
                keys = p.get("key") or []
                if isinstance(keys, str):
                    keys = [keys]
                return (
                    keys[0] if keys else "",
                    p.get("api_base") or "https://api.deepseek.com/v1",
                    p.get("model") or "deepseek-chat",
                )
    except Exception:
        pass
    return "", "https://api.deepseek.com/v1", "deepseek-chat"


def _llm(messages, max_tokens=300, temperature=0.2):
    key, base, model = _provider_conf()
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        },
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

    @filter.on_llm_request()
    async def inject(self, event: AstrMessageEvent, req: ProviderRequest):
        self._user_text[event.unified_msg_origin] = event.message_str
        identities = load_identities()
        plat = platform_key(event)
        sid = str(event.get_sender_id() or "")
        name = str(event.get_sender_name() or sid)
        owner = is_owner(event, identities)

        if owner:
            who = (
                f"【身份】现在和你说话的是{identities.get('owner_address', '爸爸')}本人"
                f"（{plat}）。这是你最亲近的人，可以叫"
                f"{identities.get('owner_address', '爸爸')}。"
            )
        else:
            who = (
                f"【身份】现在和你说话的是「{name}」（{plat}，ID {sid}），"
                f"**不是**{identities.get('owner_address', '爸爸')}。"
                f"不要叫他{identities.get('owner_address', '爸爸')}、不要撒娇，"
                "用普通朋友的语气，称呼用「你」或者对方的名字。"
            )

        req.system_prompt = who + "\n\n" + (req.system_prompt or "")
        logger.info("[memlib_bridge] %s %s -> %s", plat, sid, "owner" if owner else "guest")

        if not memlib:
            return
        try:
            block = memlib.render(view="owner" if owner else "public", limit=40, width=2000)
            if block:
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
