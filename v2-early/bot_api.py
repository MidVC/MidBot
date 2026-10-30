"""蓝色小鲸鱼 · 微信机器人（WeChatPadPro 接口版）

和旧版 bot.py 的区别：不驱动微信窗口、不需要爬 UIA/OCR、不抢鼠标焦点。
只干两件事：
  · 收：轮询 /api/Msg/Sync 拿新消息
  · 发：调 /api/Msg/SendTxt 发出去

人格、聊天节奏（不每句都回 / 只回最新 / 记忆分背景与当下 / 群聊概率接话）
全部沿用 bot.py 的逻辑。启动前的旧消息只进上下文、不回。
"""

import base64
import json
import logging
import os
import random
import re
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 共享记忆
# 个人微信、企业客服、DSH 三方共用 ~/shared-memory/memory.json
SHARED_MEM = os.path.expanduser("~/shared-memory")
if SHARED_MEM not in sys.path:
    sys.path.insert(0, SHARED_MEM)
try:
    import memlib
except Exception:
    memlib = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(BASE, "bot_api.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("xiaojingyu")

with open(os.path.join(BASE, "bot_config.json"), "r", encoding="utf-8") as f:
    CFG = json.load(f)

A = CFG.get("api", {}) or {}
API_BASE = str(A.get("base", "http://127.0.0.1:18062")).rstrip("/")
AUTHCODE = A.get("authcode", "")

# 凭证统一存在 ~/wpp-auth.json，优先级高于 bot_config.json，避免多处硬编码
_AUTH_STORE = os.path.expanduser("~/wpp-auth.json")
try:
    with open(_AUTH_STORE, "r", encoding="utf-8") as _fh:
        _cred = json.load(_fh)
    if _cred.get("authcode"):
        AUTHCODE = _cred["authcode"]
except Exception:
    pass
SELF_WXID = A.get("self_wxid", "")
API_POLL = float(A.get("poll_interval", 2.0))
API_TIMEOUT = float(A.get("timeout", 40))
WS_PORT = int(A.get("ws_port", 18089))

DEEPSEEK_KEY = CFG["api_key"]
DEEPSEEK_BASE = CFG.get("api_base", "https://api.deepseek.com").rstrip("/")
MODEL = CFG.get("model", "deepseek-chat")

SYNC_STATE = os.path.join(BASE, "synckey.json")

# ---------------------------------------------------------------- 记忆配置
MEM = CFG.get("memory", {}) or {}
MEMORY_ON = bool(MEM.get("enabled", True)) and memlib is not None
MEMORY_EXTRACT = bool(MEM.get("extract", True))
OWNER_WXIDS = set(CFG.get("owners", []) or [])
OWNER_NAMES = set(MEM.get("owner_names", []) or [])


def is_owner(who, name=None):
    if who and who in OWNER_WXIDS:
        return True
    return bool(name and name in OWNER_NAMES)

# ---------------------------------------------------------------- 语音配置
V = CFG.get("voice", {}) or {}
VOICE_ENABLED = bool(V.get("enabled", True))
TTS_VOICE = V.get("tts_voice", "zh-CN-XiaoyiNeural")
VOICE_MAX_CHARS = int(V.get("max_chars", 80))
VOICE_CHANCE = float(V.get("chance", 0.0))
FFMPEG_BIN = os.path.expanduser(
    V.get("ffmpeg") or "~/bin/ffmpeg-7.0.2-amd64-static/ffmpeg")
FFPROBE_BIN = os.path.join(os.path.dirname(FFMPEG_BIN), "ffprobe")

# ---------------------------------------------------------------- 图片/语音/表情
M = CFG.get("media", {}) or {}
DEBUG_RAW = bool(M.get("debug_raw", False))
VOICE_TRANSCRIBE = bool(M.get("voice_transcribe", True))
IMAGE_DESC = bool(M.get("image_desc", True))
RAW_LOG = os.path.join(BASE, "msgs_raw.jsonl")
RAW_MAX = 4 * 1024 * 1024

# 这些 kind 不当消息处理（系统事件、自己发的、状态类）
SKIP_KINDS = {
    "system", "revoke", "read", "typing", "status", "pat", "recall",
    "friend", "contact", "sync", "redpacket", "transfer", "pay",
}
MEDIA_LABEL = {
    "voice": "一条语音",
    "image": "一张图片",
    "img": "一张图片",
    "photo": "一张图片",
    "emoji": "一个表情包",
    "sticker": "一个表情包",
    "emojimessage": "一个表情包",
    "video": "一个视频",
    "file": "一个文件",
    "link": "一个链接",
    "card": "一张名片",
    "location": "一个位置",
    "miniprogram": "一个小程序卡片",
    "app": "一个卡片消息",
}
MEDIA_KINDS = set(MEDIA_LABEL)

# ---------------------------------------------------------------- 识图配置
VIS = CFG.get("vision", {}) or {}
VISION_ENABLED = bool(VIS.get("enabled", True))
VISION_MODEL = VIS.get("model", "deepseek-flash")
VISION_DETAIL = VIS.get("detail", "low")
VISION_MAX_TOKENS = int(VIS.get("max_tokens", 400))
VISION_PROMPT = VIS.get(
    "prompt",
    "用一两句中文说清这张图的画面：谁/什么东西、在做什么、什么情绪或场景。"
    "如果它是个表情包或梗图，直接说画面和想表达的梗，不要客套、不要解释你在描述图片。")


def load_persona():
    path = os.path.join(BASE, "AGENT.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
        if text:
            log.info("人格来源：AGENT.md（%d 字）", len(text))
            return text
    log.info("人格来源：bot_config.json")
    return CFG["persona"]


PERSONA = load_persona()

CHAT_RULES = (
    "\n\n【怎么聊天】\n"
    "- 记忆是分层的：最后几条是「刚才的对话」，更早的只算背景。注意力放在最后几条。\n"
    "- 只回应**最新那条**消息。更早的内容别复述、别总结、别主动捡回来——"
    "除非对方这一轮又提起。\n"
    "- 自己说过的话不要重复。\n"
    "- 不用每条都回。对方只是在附和或者收尾（「嗯」「哈哈」「好的」这类）、"
    "或者明显话还没说完的时候，先不接。真人聊天本来就不是每句都有回应。\n"
    "- 要回就 1-2 句，最多 3 句。不列清单、不用 Markdown、不写小作文。\n"
    "- 不要每条都反问一句。\n"
    "- 别太吵：一条消息里最多一个 emoji，感叹号别堆。\n"
    "- 如果这条你决定不回，就只输出 NO_REPLY 这七个字符，什么都别加。"
)

MEDIA_RULES = (
    "\n\n【图片/语音/表情包】\n"
    "- 对方发的非文字内容会用方括号告诉你，比如 [发来一张图片]、"
    "[发来一个表情包]、[发来一条语音，转成文字是：「…」]。\n"
    "- 语音如果给了转写文字，就照那个意思正常接话，绝不要说听不到。\n"
    "- 图片和表情包你看不到画面内容。别装懂、别描述画面，也别解释半天，"
    "一句自然的话带过就行，然后把话题接回去。\n"
    "- 收到表情包通常是在逗你或者卖萌，回一句俏皮的短话就很自然。\n"
    "- 也别每条都提「我看不到」，提一次就够了，多提很假。"
)

VOICE_RULES = (
    "\n\n【语音】\n"
    "- 你是能真的发语音条的（语音会合成你的声音，不是打字），不是只能发文字。\n"
    "- 想用「说」的方式回应时，就在回复最开头加一个标记 [[语音]]，"
    "程序会把整句合成语音条发出去，标记本身不会显示。\n"
    "- 加了标记就不要再打字重复同一句话。\n"
    "- 什么时候用：撒娇、道早安晚安、想让他听见你的声音、"
    "或者他说想听你说话的时候。正经长内容还是打字。\n"
    "- 语音要短，一句话最好；有 emoji 也没关系，会念不出来但会被去掉。"
    "- 对方打来语音/视频电话，或者发来语音，你用语音回会更自然。"
)

MAX_HISTORY = int(CFG.get("max_history", 40))
PV = CFG.get("private", {}) or {}
PRIV_DEBOUNCE = tuple(PV.get("debounce", [3, 6]))
PRIV_QUIET_FILLER = bool(PV.get("quiet_filler", True))
MAX_HISTORY = int(PV.get("max_history", MAX_HISTORY))
RECENT_WINDOW = int(PV.get("recent_window", 10))

BACKLOG_HOURS = float(CFG.get("backlog_context_hours", 24))
BACKLOG_MAX = int(CFG.get("backlog_context_max", 40))

IGNORE = set(CFG.get("ignore_names", []))
ALLOW_ONLY = set(CFG.get("allow_only", []))

G = CFG.get("group", {}) or {}
GROUP_ENABLED = bool(G.get("enabled", True))
GROUP_NAMES = list(G.get("names", ["蓝色小鲸鱼", "小鲸鱼"]))
GROUP_KEYWORDS = list(G.get("keywords", ["小鲸鱼", "鲸鱼"]))
GROUP_MIN_INTERVAL = int(G.get("min_reply_interval", 120))
GROUP_MAX_PER_10MIN = int(G.get("max_replies_per_10min", 2))
GROUP_DEBOUNCE = tuple(G.get("debounce", [3, 7]))
GROUP_CONTEXT = int(G.get("context_messages", 20))

P = CFG.get("proactive", {}) or {}
PROACTIVE_ENABLED = bool(P.get("enabled", False))
PROACTIVE_TARGET_WXID = A.get("proactive_target_wxid", "")
PROACTIVE_HOURS = tuple(P.get("active_hours", [8, 23]))
PROACTIVE_MAX_DAY = int(P.get("max_per_day", 3))
PROACTIVE_MIN_GAP = int(P.get("min_gap_minutes", 90))
PROACTIVE_QUIET_AFTER = int(P.get("quiet_after_chat_minutes", 25))
PROACTIVE_STATE = os.path.join(BASE, "proactive_state.json")

history = {}
lock = threading.Lock()
seen = set()
seen_order = []
START_TS = 0.0
BACKLOG_GRACE = 15

group_buf = {}
group_timer = {}
group_last_reply = {}
group_reply_times = {}
priv_buf = {}
priv_timer = {}
priv_last_reply = {}
backlog_seeded = {}
last_user_time = {}


# ---------------------------------------------------------------- API 层
def api(path, body, timeout=None):
    url = "%s%s?authcode=%s" % (API_BASE, path, urllib.parse.quote(AUTHCODE))
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout or API_TIMEOUT,
                                context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))


def unwrap(v):
    """接口有时把字符串包一层 {"string": "..."}。"""
    if isinstance(v, dict):
        for k in ("string", "String", "value"):
            if k in v:
                return v[k]
        return ""
    return v if v is not None else ""


def send_text(to, content, at=None):
    body = {"ToWxid": to, "Content": content, "Type": 1}
    if at:
        body["At"] = at
    res = api("/api/Msg/SendTxt", body)
    if not res.get("Success"):
        log.warning("发送失败(%s): %s", to, res.get("Message"))
    return bool(res.get("Success"))


VOICE_TAG_RE = re.compile(r"\[\[\s*(?:语音|voice|audio)\s*\]\]", re.I)
EMOJI_RE = re.compile(
    "[" "\U0001F300-\U0001FAFF" "\U00002700-\U000027BF" "\U0001F000-\U0001F2FF"
    "\u2600-\u26FF" "\uFE0F" "\u200D" "\u2B50" "\u2764" "]+", re.S)


def tidy_for_speech(text):
    """去掉标记、emoji、网址，留下能念的字。"""
    t = VOICE_TAG_RE.sub("", text or "")
    t = EMOJI_RE.sub("", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\s+", " ", t).strip(" ，。、,.~～…")
    return t[:VOICE_MAX_CHARS]


def text_to_amr(text, mp3_path, amr_path):
    """edge-tts 合成 mp3，再用静态 ffmpeg 转 AMR-NB（微信 Type=0）。"""
    import asyncio

    import edge_tts

    asyncio.run(edge_tts.Communicate(text, TTS_VOICE).save(mp3_path))
    subprocess.run([FFMPEG_BIN, "-y", "-i", mp3_path, "-ac", "1", "-ar", "8000",
                    "-c:a", "libopencore_amrnb", "-b:a", "12.2k", amr_path],
                   check=True, capture_output=True, timeout=120)
    return amr_path


def amr_duration_ms(amr_path):
    """语音时长（毫秒）。先用 ffprobe，失败就按 AMR 帧数估算。"""
    try:
        out = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", amr_path],
            check=True, capture_output=True, text=True, timeout=30).stdout.strip()
        ms = int(float(out) * 1000)
        if ms > 0:
            return max(1000, min(60000, ms))
    except Exception:
        pass
    try:
        size = os.path.getsize(amr_path)
        ms = int((max(0, size - 6) / 32.0) * 20)   # 12.2kbps: 32 字节/20ms
        return max(1000, min(60000, ms))
    except Exception:
        return 3000


def send_voice(to, content):
    """合成语音条发出去。返回是否成功。"""
    if not VOICE_ENABLED:
        return False
    speak = tidy_for_speech(content)
    if not speak:
        return False
    tag = "%s-%d" % (int(time.time() * 1000), threading.get_ident())
    mp3 = os.path.join(BASE, ".v-%s.mp3" % tag)
    amr = os.path.join(BASE, ".v-%s.amr" % tag)
    try:
        text_to_amr(speak, mp3, amr)
        with open(amr, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        body = {"ToWxid": to, "Base64": b64, "Type": 0,
                "VoiceTime": amr_duration_ms(amr)}
        res = {}
        for attempt in (1, 2, 3):
            try:
                res = api("/api/Msg/SendVoice", body)
            except Exception as exc:
                log.warning("语音发送第 %d 次异常: %s", attempt, exc)
                res = {}
            if res.get("Success"):
                break
            if attempt < 3:
                log.info("语音发送第 %d 次失败（%s），重试", attempt,
                         res.get("Message") or "无响应")
                time.sleep(1.5 * attempt)
        if not res.get("Success"):
            log.warning("语音发送失败(%s): %s", to, res.get("Message"))
            return False
        log.info("语音 [%s]: %s", to, speak[:80])
        return True
    except Exception:
        log.warning("语音流程异常", exc_info=True)
        return False
    finally:
        for p in (mp3, amr):
            try:
                os.remove(p)
            except Exception:
                pass


WANT_VOICE_RE = re.compile(
    r"语音|听.{0,4}(声音|说)|(说|讲|念|读)(一|几)?句|发.{0,3}声|"
    r"听听你|用嘴|开口|record|voice",
    re.I)


def asks_for_voice(texts):
    """对方是不是明确要听语音。"""
    for t in texts:
        if WANT_VOICE_RE.search(t or ""):
            return True
    return False


def fetch_ticket():
    """用 Access Token 换一个 5 分钟有效的 WebSocket 连接票据。"""
    url = API_BASE + "/api/Runtime/WebSocketTicket"
    req = urllib.request.Request(
        url, data=b"{}",
        headers={"Content-Type": "application/json", "X-Access-Token": AUTHCODE},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20,
                                context=ssl.create_default_context()) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("Success"):
        raise RuntimeError("取票据失败: %s" % data.get("Message"))
    return data["Data"]["ticket"], data["Data"].get("websocket_path", "/ws/sync")


def ws_url(ticket, path):
    host = urllib.parse.urlparse(API_BASE).hostname or "127.0.0.1"
    return "ws://%s:%d%s?ticket=%s" % (host, WS_PORT, path, urllib.parse.quote(ticket))


# ---------------------------------------------------------------- 模型层
def deepseek(messages, max_tokens=300, temperature=1.0, model=None, extra=None):
    payload = {
        "model": model or MODEL, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens, "stream": False,
    }
    if extra:
        payload.update(extra)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_BASE + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + DEEPSEEK_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90,
                                context=ssl.create_default_context()) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data["choices"][0]["message"]["content"] or "").strip()


def tidy_reply(text):
    if not text:
        return ""
    text = re.sub(r"^\s*(assistant|蓝色小鲸鱼|小鲸鱼)\s*[:：]\s*", "", text, flags=re.I)
    text = text.strip().strip('"“”').strip()
    if text.upper().startswith("NO_REPLY"):
        return "NO_REPLY"
    if len(text) > 140:
        parts = re.split(r"(?<=[。！？!?~～\n])", text)
        picked, total = [], 0
        for p in parts:
            p = p.strip()
            if not p:
                continue
            picked.append(p)
            total += len(p)
            if total >= 80 or len(picked) >= 3:
                break
        text = "".join(picked).strip() or text
    if len(text) > 140:
        text = text[:140].rstrip()
    return text


FILLER_RE = re.compile(
    r"^[\s，。！？、,.!?~～…·\-]*("
    r"嗯+|哦+|噢+|喔+|额+|呃+|啊+|嘞|好+|好的|好呗|好嘞|好呀|行|可以|收到|ok|okay|"
    r"了解|懂了?|明白|辛苦了|谢谢|谢啦|多谢|"
    r"哈+|h+|hh+|233+|笑死|确实|是的|对的|对啊|没错|牛逼|牛|厉害|绝了|6+|好耶"
    r")[\s，。！？、,.!?~～…·🐳✨😆👍👌🤣😂]*$",
    re.I,
)


def is_filler(text):
    t = re.sub(r"@\S+\s*", "", str(text)).strip()
    if not t or len(t) > 10:
        return False
    return bool(FILLER_RE.match(t))


# ---------------------------------------------------------------- 记忆层
def remember(who, role, content, ts=None, backlog=False):
    with lock:
        hist = history.setdefault(who, [])
        if hist and hist[-1]["role"] == role and hist[-1].get("backlog") == backlog:
            merged = hist[-1]["content"] + "\n" + content
            hist[-1]["content"] = merged[-600:]
            hist[-1]["ts"] = ts or hist[-1].get("ts") or time.time()
        else:
            hist.append({"role": role, "content": content,
                         "ts": ts or time.time(), "backlog": backlog})
        del hist[:-MAX_HISTORY]


def render_background(entries):
    lines = []
    for e in entries:
        ts = e.get("ts") or 0
        clock = time.strftime("%m-%d %H:%M", time.localtime(ts)) if ts else ""
        who = "对方" if e["role"] == "user" else "你"
        text = e["content"].replace("\n", " / ")
        if len(text) > 80:
            text = text[:80] + "…"
        lines.append(("%s %s：%s" % (clock, who, text)).strip())
    joined = "\n".join(lines)
    if len(joined) > 1500:
        joined = "…\n" + joined[-1500:]
    return joined


def build_private_messages(chat_key, latest_text):
    with lock:
        hist = list(history.get(chat_key, []))
    recent = hist[-RECENT_WINDOW:]
    older = hist[:-RECENT_WINDOW]

    rules = CHAT_RULES + MEDIA_RULES + (VOICE_RULES if VOICE_ENABLED else "")
    messages = [{"role": "system", "content": PERSONA + rules}]
    if MEMORY_ON:
        block = memlib.render(view="owner" if is_owner(chat_key) else "public",
                              limit=40)
        if block:
            messages.append({
                "role": "system",
                "content": "【你记得的事】\n" + block +
                           "\n（这些是你长期记住的，自然地用，别一口气全说出来。）",
            })
    if older:
        messages.append({
            "role": "system",
            "content": ("【更早的聊天｜只当背景】\n%s\n"
                        "（这些是之前发生的事。别复述、别总结、别主动提起，"
                        "除非对方这一轮又说到。）" % render_background(older)),
        })
    for e in recent:
        messages.append({"role": e["role"], "content": e["content"]})
    messages.append({"role": "user", "content": latest_text})
    return messages


def ask_private(chat_key, texts):
    joined = "\n".join(texts)
    if len(texts) > 1:
        latest = ("（对方在几秒内连着发了 %d 条，当成一口气说完的一整段话）\n" % len(texts)) + \
                 "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(texts))
    else:
        latest = joined
    reply = tidy_reply(deepseek(build_private_messages(chat_key, latest)))
    remember(chat_key, "user", joined)
    if reply and reply != "NO_REPLY":
        remember(chat_key, "assistant", reply)
        return reply
    return None


# ---------------------------------------------------------------- 私聊
def on_private(who, name, text, raw=None):
    with lock:
        buf = priv_buf.setdefault(who, [])
        buf.append({"text": text, "raw": raw})
        del buf[:-6]

    old = priv_timer.pop(who, None)
    if old is not None:
        try:
            old.cancel()
        except Exception:
            pass

    timer = threading.Timer(random.uniform(*PRIV_DEBOUNCE), run_private_reply,
                            args=(who, name))
    timer.daemon = True
    priv_timer[who] = timer
    timer.start()
    log.info("私聊 [%s]: %s", name, text[:100])


def run_private_reply(who, name):
    try:
        priv_timer.pop(who, None)
        with lock:
            items = list(priv_buf.get(who, []))
            priv_buf[who] = []
        if not items:
            return
        texts = []
        for it in items:
            t = it["text"]
            if it.get("raw"):
                t = resolve_media(it["raw"], t)
            texts.append(t)
        if PRIV_QUIET_FILLER and all(is_filler(t) for t in texts):
            if time.time() - priv_last_reply.get(who, 0) < 300:
                log.info("[私聊 %s] 只是附和，不接话", name)
                return
        reply = ask_private(who, texts)
        if not reply:
            log.info("[私聊 %s] 这条不回", name)
            return
        want_voice = bool(VOICE_TAG_RE.search(reply))
        if want_voice:
            reply = VOICE_TAG_RE.sub("", reply).strip()
        if not reply:
            return
        log.info("回复 [%s]: %s", name, reply[:200])

        use_voice = VOICE_ENABLED and (
            want_voice
            or asks_for_voice(texts)
            or (VOICE_CHANCE > 0 and random.random() < VOICE_CHANCE)
        )
        if use_voice and len(tidy_for_speech(reply)) > VOICE_MAX_CHARS:
            if want_voice:
                log.info("[私聊 %s] 这条太长，改发文字", name)
            use_voice = False

        if use_voice:
            if send_voice(who, reply):
                priv_last_reply[who] = time.time()
                spawn_extract(who, name, texts, reply)
                return
            log.info("[私聊 %s] 语音没发成，退回文字", name)
        if send_text(who, reply):
            priv_last_reply[who] = time.time()
            spawn_extract(who, name, texts, reply)
    except Exception:
        log.exception("私聊回复出错")


def spawn_extract(who, name, texts, reply):
    """回完之后异步把值得记的事写进共享记忆。"""
    if not (MEMORY_ON and MEMORY_EXTRACT):
        return
    joined = "\n".join(texts)
    if len(joined) + len(reply) < 12:
        return
    try:
        threading.Thread(
            target=memlib.extract,
            args=(deepseek, joined, reply),
            kwargs={"source": "wpp",
                    "scope": "owner" if is_owner(who, name) else "public",
                    "logger": log},
            daemon=True).start()
    except Exception:
        log.warning("[记忆] 起线程失败", exc_info=True)


# ---------------------------------------------------------------- 群聊
def mentions_me(text):
    return any("@" + n in text for n in GROUP_NAMES)


def hits_keyword(text):
    return any(k in text for k in GROUP_KEYWORDS)


def can_reply_group(g):
    now = time.time()
    if now - group_last_reply.get(g, 0) < GROUP_MIN_INTERVAL:
        return False
    times = [t for t in group_reply_times.get(g, []) if now - t < 600]
    group_reply_times[g] = times
    return len(times) < GROUP_MAX_PER_10MIN


def mark_reply(g):
    now = time.time()
    group_last_reply[g] = now
    group_reply_times.setdefault(g, []).append(now)


def judge_group_reply(g, is_at):
    with lock:
        buf = list(group_buf.get(g, []))[-GROUP_CONTEXT:]
    transcript = "\n".join("%s：%s" % (s or "某人", t) for _ts, s, t in buf)

    if is_at:
        instruction = (
            "有人在群里 @ 了你，你**应该**回一句。直接输出你要发的话，"
            "不要解释、不要加引号。只针对**最新那条**说，1 句最好，最多 2 句；"
            "已经把话说过的就别重复，别把翻篇的旧话题再捡回来。"
        )
    else:
        instruction = (
            "你在群里看着大家聊天。判断一下：**现在**接一句话自不自然？\n"
            "正常人的做法是——大部分时候不说话；只有话题刚好和你有关、有人问了个问题、"
            "或者气氛适合接个梗的时候，才会插一句。刚有人说完话、话题已经翻篇、"
            "别人在互相聊私事、或者你刚才已经说过类似的话，就不要插嘴。\n"
            "记录前面那些是更早的，只当背景；只接最新这几条的内容，别回头接翻篇的话。\n"
            "如果要说话：直接输出你要发的那句话（1 句，最多 2 句，别 @ 任何人，别解释）。\n"
            "如果不说话：只输出 NO_REPLY 这七个字符，什么都别加。"
        )

    messages = [
        {"role": "system", "content": PERSONA + "\n\n【群聊场景】你正在一个微信群里。"},
        {"role": "user", "content": "最近的群聊记录：\n%s\n\n%s" % (transcript, instruction)},
    ]
    out = deepseek(messages, max_tokens=200)
    if not out:
        return None
    first = tidy_reply(out.strip().splitlines()[0])
    if not first or first == "NO_REPLY" or first.startswith("不回复"):
        return None
    first = re.sub(r"^(回复|回答)[:：]\s*", "", first)
    return first.strip().strip('"“”') or None


def schedule_group(g, delay=None):
    old = group_timer.pop(g, None)
    if old is not None:
        try:
            old.cancel()
        except Exception:
            pass
    if delay is None:
        delay = random.uniform(*GROUP_DEBOUNCE)
    t = threading.Timer(delay, run_group_judgement, args=(g,))
    t.daemon = True
    group_timer[g] = t
    t.start()


def run_group_judgement(g):
    try:
        with lock:
            buf = group_buf.get(g, [])
            if not buf:
                return
            last_ts = buf[-1][0]
        if time.time() - last_ts < 2.0:
            schedule_group(g, delay=2.5)
            return
        if not can_reply_group(g):
            log.info("[群 %s] 冷却中，不接话", g)
            return
        text = judge_group_reply(g, is_at=False)
        if not text:
            log.info("[群 %s] 判断：不插话", g)
            return
        log.info("[群 %s] 主动接话：%s", g, text[:150])
        if send_text(g, text):
            mark_reply(g)
    except Exception:
        log.exception("群聊判断出错")


def on_group(g, sender, text, at_me=False):
    with lock:
        group_buf.setdefault(g, []).append((time.time(), sender, text))
        group_buf[g] = group_buf[g][-120:]
    log.info("[群 %s] %s: %s", g, sender, text[:100])

    if at_me or mentions_me(text):
        log.info("[群 %s] 被 @ 了，直接回", g)
        try:
            old = group_timer.pop(g, None)
            if old is not None:
                old.cancel()
            reply = judge_group_reply(g, is_at=True)
            if reply:
                log.info("[群 %s] 回复 @：%s", g, reply[:150])
                if send_text(g, reply):
                    mark_reply(g)
        except Exception:
            log.exception("群 @ 回复失败")
        return

    if hits_keyword(text):
        schedule_group(g, delay=random.uniform(1.5, 3.0))
    else:
        schedule_group(g)


# ---------------------------------------------------------------- 消息入口
def seed_backlog(who, role, text, ct, is_group=False, sender=""):
    if is_group:
        with lock:
            buf = group_buf.setdefault(who, [])
            buf.append((ct or time.time(), sender, text))
            group_buf[who] = buf[-120:]
        return
    with lock:
        n = backlog_seeded.get(who, 0)
        if n >= BACKLOG_MAX:
            return
        backlog_seeded[who] = n + 1
    remember(who, role, text, ct, backlog=True)


def dump_raw(m):
    """把收到的原始消息追加到 msgs_raw.jsonl，方便摸清字段。"""
    if not DEBUG_RAW:
        return
    try:
        if os.path.exists(RAW_LOG) and os.path.getsize(RAW_LOG) > RAW_MAX:
            os.replace(RAW_LOG, RAW_LOG + ".1")
        with open(RAW_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "msg": m},
                                ensure_ascii=False) + "\n")
    except Exception:
        pass


def media_payload(m, kind):
    """消息里真正承载图片/语音参数的那个对象。"""
    for key in (kind, "voice", "image", "img", "emoji", "sticker",
                "video", "file", "app", "card", "location"):
        v = m.get(key)
        if isinstance(v, dict) and v:
            return v
    return {}


def describe_media(m, kind):
    """把非文字消息变成一句能读的说明。"""
    kind = (kind or "").lower()
    payload = media_payload(m, kind)
    label = MEDIA_LABEL.get(kind)

    if not label:
        # kind 不认识，就看消息里带了什么对象
        for guess, name in (("voice", "一条语音"), ("image", "一张图片"),
                            ("emoji", "一个表情包"), ("video", "一个视频"),
                            ("file", "一个文件")):
            if isinstance(m.get(guess), dict) and m.get(guess):
                label = name
                break

    if not label:
        return ""

    if label == "一条语音":
        secs = payload.get("duration_ms")
        if isinstance(secs, (int, float)) and secs:
            secs = secs / 1000.0
        else:
            secs = payload.get("voice_length") or payload.get("duration") or \
                payload.get("time")
            if not secs:
                raw_len = payload.get("length")
                if isinstance(raw_len, (int, float)) and raw_len:
                    secs = raw_len / 1600.0 if raw_len > 200 else raw_len
        try:
            secs = float(secs)
        except (TypeError, ValueError):
            secs = 0
        head = "一条语音"
        if 1 <= secs <= 120:
            head = "一条语音，%d 秒" % round(secs)
        text = voice_transcript(m)
        if text:
            return "[发来%s，转成文字是：「%s」]" % (head, text[:300])
        return "[发来%s]" % head

    if label == "一个表情包":
        fmt = str(payload.get("format") or "")
        w, h = payload.get("width"), payload.get("height")
        extra = "动图" if fmt == "2" else "静态图"
        if isinstance(w, int) and isinstance(h, int) and w and h:
            extra += " %dx%d" % (w, h)
        return "[发来一个表情包（%s）]" % extra

    if label == "一个文件":
        fname = payload.get("file_name") or payload.get("name") or ""
        if fname:
            return "[发来一个文件：%s]" % str(fname)[:60]

    return "[发来%s]" % label


def transcribe_voice(m):
    """用 WPP 的语音转写把收到的语音变成文字。"""
    if not VOICE_TRANSCRIBE:
        return ""
    try:
        res = api("/api/Voice/MessageTranscribe", m, timeout=60)
    except Exception:
        log.warning("语音转写请求失败", exc_info=True)
        return ""
    if not res.get("Success", True):
        log.info("语音转写未成功: %s", str(res.get("Message"))[:200])
    data = res.get("Data") or {}
    if isinstance(data, dict):
        for key in ("text", "Text", "content", "Content",
                    "transcribe", "transcription", "result", "Result"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        log.info("语音转写返回结构: %s", json.dumps(data, ensure_ascii=False)[:400])
    return ""


def resolve_media(raw, placeholder):
    """真正要回的时候，再补上能读懂的内容（避免堵住收消息的线程）。"""
def voice_transcript(raw):
    """WPP 已经在 voice 里给了转写文字，优先用它。"""
    v = raw.get("voice") or {}
    t = v.get("transcript") or ""
    if isinstance(t, str) and t.strip():
        return t.strip()
    c = str(raw.get("content") or "").strip()
    if v and c and not c.startswith("收"):
        return c
    return ""


def download_image_b64(raw):
    """把微信图片下载下来，返回 base64（走 CdnDownloadImage）。"""
    img = raw.get("image") or {}
    ctxs = img.get("cdn_download_contexts") or []
    if not ctxs:
        return ""
    pick = next((c for c in ctxs if c.get("variant") == "standard"), ctxs[0])
    endpoint = pick.get("endpoint") or "/api/Tools/CdnDownloadImage"
    body = {k: v for k, v in pick.items() if k not in ("endpoint", "variant")}
    try:
        res = api(endpoint, body, timeout=120)
    except Exception:
        log.warning("图片下载失败", exc_info=True)
        return ""
    data = res.get("Data") or {}
    b64 = data.get("Image") or data.get("image") or ""
    if not isinstance(b64, str) or not b64:
        log.info("图片下载返回: %s", json.dumps(res, ensure_ascii=False)[:300])
        return ""
    return b64


def describe_image(raw):
    """用 deepseek-flash 看一眼这张图。"""
    if not VISION_ENABLED:
        return ""
    b64 = download_image_b64(raw)
    if not b64:
        return ""
    messages = [{"role": "user", "content": [
        {"type": "text", "text": VISION_PROMPT},
        {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + b64,
            "detail": VISION_DETAIL,
        }},
    ]}]
    try:
        out = deepseek(messages, max_tokens=VISION_MAX_TOKENS, temperature=0.2,
                       model=VISION_MODEL,
                       extra={"thinking": {"type": "disabled"}})
    except Exception:
        log.warning("识图请求失败", exc_info=True)
        return ""
    out = (out or "").strip().strip('"“”')
    return out[:300]


def resolve_media(raw, placeholder):
    """真正要回的时候，再补上能读懂的内容（避免堵住收消息的线程）。"""
    kind = str(raw.get("kind") or "").lower()
    if kind == "voice":
        text = voice_transcript(raw) or transcribe_voice(raw)
        if text:
            return "[发来一条语音，转成文字是：「%s」]" % text[:300]
        return placeholder
    if kind in ("image", "img", "photo") and IMAGE_DESC:
        desc = describe_image(raw)
        if desc:
            return "[发来一张图片，画面是：%s]" % desc
    return placeholder


def handle(m):
    """处理一条 wechatpad.message.v2 消息。"""
    try:
        mid = m.get("id") or m.get("new_msg_id")
        conv = m.get("conversation_id") or ""
        direction = m.get("direction") or ""
        kind = str(m.get("kind") or "")
        text = str(m.get("content") or "").strip()
        created = float(m.get("created_at") or 0)
        is_group = bool(m.get("is_group"))
        is_media = False

        if direction != "incoming":
            return                      # 自己发的、系统状态都不处理
        if conv in ("weixin", "fmessage", "medianote", "weixinreminder"):
            return

        dump_raw(m)

        if kind == "text":
            if not text:
                return
        elif kind in SKIP_KINDS:
            return
        else:
            text = describe_media(m, kind)
            if not text:
                log.info("忽略消息类型 [%s]: %s", kind, json.dumps(
                    m, ensure_ascii=False)[:400])
                return
            is_media = True

        with lock:
            if mid in seen:
                return
            seen.add(mid)
            seen_order.append(mid)
            if len(seen_order) > 5000:
                for k in seen_order[:2000]:
                    seen.discard(k)
                del seen_order[:2000]

        push = str(m.get("push_content") or "")
        sender = push.split(" : ")[0].strip() if " : " in push else (m.get("sender_id") or "对方")
        ctx = m.get("message_context") or {}
        at_me = SELF_WXID in (ctx.get("mentioned_user_ids") or [])

        # 启动前的旧消息：只记不答
        if created and START_TS and created < START_TS - BACKLOG_GRACE:
            if created < START_TS - BACKLOG_HOURS * 3600:
                return
            seed_backlog(conv, "user", text, created, is_group, sender)
            return

        last_user_time[conv] = time.time()
        if is_media:
            log.info("收到 [%s/%s]: %s", kind, sender, text[:120])

        if is_group:
            if GROUP_ENABLED:
                on_group(conv, sender, text, at_me)
        else:
            if conv in IGNORE:
                return
            if ALLOW_ONLY and conv not in ALLOW_ONLY:
                return
            on_private(conv, sender, text, m if is_media else None)
    except Exception:
        log.exception("处理消息出错")


def on_frame(raw):
    try:
        obj = json.loads(raw)
    except Exception:
        return
    data = obj.get("Data") or {}
    payload = data.get("data") or {}
    if isinstance(payload, dict):
        for m in (payload.get("messages") or []):
            handle(m)


def ws_loop():
    """连上实时推送通道；断了就重连（票据 5 分钟过期，每次重连都换新票）。"""
    global START_TS
    from websockets.sync.client import connect

    START_TS = time.time()
    log.info("开始监听实时消息（ws://<host>:%d/ws/sync）", WS_PORT)
    while True:
        try:
            ticket, path = fetch_ticket()
            with connect(ws_url(ticket, path), ping_interval=20,
                         max_size=8 * 1024 * 1024, open_timeout=20) as ws:
                log.info("实时通道已连接")
                while True:
                    try:
                        raw = ws.recv(timeout=90)
                    except TimeoutError:
                        continue
                    on_frame(raw)
        except Exception as exc:
            log.warning("实时通道断开: %s，5 秒后重连", exc)
            time.sleep(5)


# ---------------------------------------------------------------- 主动消息
def load_state():
    try:
        with open(PROACTIVE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(st):
    try:
        with open(PROACTIVE_STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        log.warning("保存主动消息状态失败")


def compose_proactive():
    with lock:
        hist = [e for e in history.get(PROACTIVE_TARGET_WXID, [])
                if not e.get("backlog")][-8:]
    convo = "\n".join(
        ("对方：%s" % m["content"]) if m["role"] == "user" else ("你：%s" % m["content"])
        for m in hist
    ) or "（最近没聊过）"
    now = time.localtime()
    clock = "%02d:%02d" % (now.tm_hour, now.tm_min)
    day = "%d月%d日 周%s" % (now.tm_mon, now.tm_mday,
                            "一二三四五六日"[now.tm_wday])
    parts = [
        "现在是 %s %s。对方没有在跟你说话，你想主动给他发一条微信。" % (day, clock),
        "最近的聊天：\n%s" % convo,
    ]
    if MEMORY_ON:
        block = memlib.render(view="owner", limit=25, width=900)
        if block:
            parts.append(
                "你长期记得关于他的事：\n%s\n"
                "（优先拿这些当由头：他明天要办的事、他的习惯、最近在忙什么。"
                "但要自然，别把记忆原样念出来，也别一口气全说。）" % block)
    parts.append(
        "要求：\n"
        "1. 像女儿随手发的一条，不是模板问候。\n"
        "2. 只发一句话，最多两句。\n"
        "3. 别总是「在干嘛」「吃饭了吗」这种空话；有记忆就用记忆。\n"
        "4. 别每次同一个句式，也别每次都追问。\n"
        "5. 直接输出要发的内容，不要引号、不要解释。"
    )
    instruction = "\n\n".join(parts)
    out = deepseek([{"role": "system", "content": PERSONA},
                    {"role": "user", "content": instruction}],
                   max_tokens=120, temperature=1.2)
    if not out:
        return ""
    text = out.strip().splitlines()[0].strip().strip('"“”')
    recent_mine = [m["content"] for m in hist if m["role"] == "assistant"][-3:]
    if text and text in recent_mine:
        return ""
    return text


def proactive_loop():
    if not PROACTIVE_TARGET_WXID:
        log.info("未配置 proactive_target_wxid，主动消息不启用")
        return
    log.info("主动消息已开启：目标=%s", PROACTIVE_TARGET_WXID)
    while True:
        try:
            time.sleep(240)
            now = time.time()
            if now - START_TS < 30 * 60:
                continue
            hour = time.localtime(now).tm_hour
            if not (PROACTIVE_HOURS[0] <= hour < PROACTIVE_HOURS[1]):
                continue
            st = load_state()
            today = time.strftime("%Y-%m-%d")
            if st.get("date") != today:
                st = {"date": today, "count": 0, "last": 0}
            if st.get("count", 0) >= PROACTIVE_MAX_DAY:
                continue
            if now - float(st.get("last", 0)) < PROACTIVE_MIN_GAP * 60:
                continue
            if now - last_user_time.get(PROACTIVE_TARGET_WXID, 0) < PROACTIVE_QUIET_AFTER * 60:
                continue
            windows = [(8, 10, 0.45), (11, 13, 0.35), (15, 18, 0.25), (19, 23, 0.40)]
            p = 0.08
            for a, b, w in windows:
                if a <= hour < b:
                    p = w
                    break
            if random.random() > p:
                continue
            text = compose_proactive()
            if not text:
                continue
            log.info("[主动] -> %s: %s", PROACTIVE_TARGET_WXID, text[:150])
            if send_text(PROACTIVE_TARGET_WXID, text):
                st["count"] = int(st.get("count", 0)) + 1
                st["last"] = now
                save_state(st)
                remember(PROACTIVE_TARGET_WXID, "assistant", text)
        except Exception:
            log.exception("主动消息失败")


def memory_maint_loop():
    """每天 04:00 整理共享记忆（多个 bot 都跑，靠共享锁保证只跑一次）。"""
    while True:
        try:
            lt = time.localtime()
            if MEMORY_ON and lt.tm_hour == 4 and lt.tm_min < 10:
                res = memlib.daily_consolidate(deepseek, logger=log)
                log.info("[记忆] 每日整理：%s", res)
                time.sleep(600)
            else:
                time.sleep(120)
        except Exception:
            log.warning("[记忆] 维护线程出错", exc_info=True)
            time.sleep(300)


def main():
    log.info("蓝色小鲸鱼（接口版）启动，模型=%s，服务=%s", MODEL, API_BASE)
    if MEMORY_ON:
        st = memlib.stats()
        log.info("[记忆] 共享库 %d 条，来源 %s", st["total"], st["by_source"])
    try:
        res = api("/api/Login/GetCacheInfo", {})
        data = res.get("Data") or {}
        log.info("当前账号: %s (%s) 在线=%s",
                 data.get("nickname"), data.get("wxid"), data.get("login_active"))
    except Exception as exc:
        log.warning("查询登录状态失败: %s", exc)

    if PROACTIVE_ENABLED:
        threading.Thread(target=proactive_loop, daemon=True).start()
    if MEMORY_ON:
        threading.Thread(target=memory_maint_loop, daemon=True).start()
    ws_loop()


if __name__ == "__main__":
    main()
