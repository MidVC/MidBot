import json
import os
import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

BASE = os.path.dirname(os.path.abspath(__file__))
WL_PATH = os.path.join(BASE, "whitelist.json")
_cache = {"t": 0.0, "ids": set()}


def whitelist_ids() -> set:
    if time.time() - _cache["t"] < 3:
        return _cache["ids"]
    ids = set()
    try:
        with open(WL_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        ids = {str(x).strip() for x in (data.get("groups") or []) if str(x).strip()}
    except Exception:
        ids = set()
    _cache["ids"] = ids
    _cache["t"] = time.time()
    return ids


class GroupWhitelist(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=1000)
    async def gate(self, event: AstrMessageEvent):
        """不在白名单的群，直接掐掉，不进 LLM。"""
        gid = str(event.get_group_id() or "").strip()
        if gid and gid in whitelist_ids():
            return
        logger.info(f"[group_whitelist] 群 {gid} 不在白名单，忽略")
        event.stop_event()
