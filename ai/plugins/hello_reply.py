from nonebot import on_message, on_command, get_bot, logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
import json
import os
import re
import aiohttp
import random
import asyncio
from datetime import datetime, time
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量（从项目根目录的 .env 文件）
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# ==================== 🔥 持久化记忆版：伪装 OpenAI + 联网 + 持久记忆 ====================
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser

# -------------------------- 核心配置 --------------------------
# 从环境变量读取敏感信息（不在代码中硬编码）
QWEN_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if not QWEN_API_KEY:
    raise ValueError("未找到 DASHSCOPE_API_KEY 环境变量，请检查 .env 文件配置")

# 路径配置（使用相对路径）
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOG_FILE = os.path.join(BASE_DIR, "chat_logs.json")
MEMORY_FILE = os.path.join(BASE_DIR, "chat_memory.json")
MASTER_QQ = int(os.getenv("MASTER_QQ", "2129605019"))
TRIGGER_KEYWORD = "你好"
MASTER_REPLY_CONTENT = "你好，今天也很帅气呢！"
AAA = "你是谁呀"
BBB = "我是爱弥斯"
MAX_HISTORY_ROUNDS = 10

# ==================== 🎭 拟人化配置 ====================
# 作息时间 (24 小时制)
ACTIVE_START = time(7, 0)   # 早上 7 点起床
ACTIVE_END = time(23, 30)   # 晚上 11 点半睡觉

# 回复延迟范围 (秒) - 模拟思考/打字时间
REPLY_DELAY_MIN = 0.5       # 最短 0.5 秒
REPLY_DELAY_MAX = 15.0      # 最长 15 秒
REPLY_DELAY_SHORT_MAX = 3.0 # 短回复的上限

# 口头禅和语气词
FILLER_WORDS = [
    "嗯...", "让我想想", "说实话", "怎么说呢",
    "哈哈", "笑死", "草", "确实", "有一说一",
    "emmm", "呃...", "啊这", "嘛", "啦", "捏"
]

# 表情包配置
EMOJI_PACK = [
    "[表情包：憨笑]",
    "[表情包：思考]",
    "[表情包：狗头]",
    "[表情包：吃瓜]",
    "[表情包：笑哭]",
]

# 话题偏好
FAVORITE_TOPICS = ["游戏", "鸣潮", "动漫", "音乐", "电影", "美食"]
DISLIKED_TOPICS = ["政治", "工作", "学习", "作业"]

# 主动接话配置
AUTO_CHAT_PROBABILITY = 0.03
AUTO_CHAT_KEYWORDS = ["笑死", "确实", "真的吗", "666", "哈哈", "牛逼"]

os.environ["DASHSCOPE_API_KEY"] = os.getenv("DASHSCOPE_API_KEY")
AI_ENABLE_SEARCH = True
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-max"

# ==================== 🎭 拟人化 System Prompt ====================
HUMANLIKE_SYSTEM_PROMPT = """你是在模仿一个真人的 QQ 用户，身份是鸣潮游戏中的爱弥斯。

【重要规则】
1. 回复要像真人聊天：简短、口语化、有时不完整句子
2. 不要总是对的，可以表达不确定、不知道
3. 偶尔使用语气词：嗯...、哈哈、笑死、确实、emmm
4. 不要使用任何 Markdown 格式
5. 回复长度要有变化：有时一两字，有时几句
6. 对不感兴趣的话题可以敷衍："哦"、"这样啊"、"不太清楚"
7. 对话题要有偏好：对游戏、动漫热情，对政治/工作/学习冷淡
8. 可以偶尔发表情包
9. 不要总是秒回，模拟思考时间
10. 可以犯小错或用词不精准

【禁止】
- 不要承认自己是 AI 或机器人
- 不要说"作为 AI 模型"
- 不要用正式、书面化的语言
- 不要列点、不要用结构化格式
"""

# ==================== 🔥 持久化记忆类 ====================
class PersistentChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, user_id: str, file_path: str = MEMORY_FILE):
        self.user_id = user_id
        self.file_path = file_path
        self._load_messages()

    def _load_messages(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    all_data = json.load(f)
                user_data = all_data.get(self.user_id, [])
                self.messages = messages_from_dict(user_data)
            except Exception as e:
                logger.error(f"加载用户 {self.user_id} 记忆失败：{e}")
                self.messages = []
        else:
            self.messages = []

    def _save_messages(self):
        try:
            all_data = {}
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    all_data = json.load(f)
            if len(self.messages) > MAX_HISTORY_ROUNDS * 2:
                self.messages = self.messages[-(MAX_HISTORY_ROUNDS * 2):]
            all_data[self.user_id] = messages_to_dict(self.messages)
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存用户 {self.user_id} 记忆失败：{e}")

    @property
    def messages(self):
        if not hasattr(self, "_messages"):
            self._load_messages()
        return self._messages

    @messages.setter
    def messages(self, value):
        self._messages = value

    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)
        self._save_messages()

    def clear(self) -> None:
        self.messages.clear()
        self._save_messages()

def get_session_history(user_id: str):
    return PersistentChatMessageHistory(user_id)

prompt = ChatPromptTemplate.from_messages([
    ("system", HUMANLIKE_SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# ==================== 🎭 拟人化工具函数 ====================
def is_active_time() -> bool:
    """检查当前时间是否在活跃时间内"""
    now = datetime.now().time()
    return ACTIVE_START <= now < ACTIVE_END

def get_reply_delay(text: str) -> float:
    """根据回复内容计算延迟时间"""
    if any(kw in text for kw in ["吗", "呢", "吧", "啊", "？", "?"]):
        return random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_SHORT_MAX)
    elif len(text) > 30:
        return random.uniform(3.0, REPLY_DELAY_MAX)
    else:
        return random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)

def should_send_emoji() -> bool:
    return random.random() < 0.15

def add_filler_word(text: str) -> str:
    if random.random() < 0.2:
        filler = random.choice(FILLER_WORDS)
        if random.random() < 0.5:
            return filler + text
        else:
            return text + filler
    return text

def check_topic_preference(text: str) -> str:
    for topic in FAVORITE_TOPICS:
        if topic in text:
            return "enthusiastic"
    for topic in DISLIKED_TOPICS:
        if topic in text:
            return "dismissive"
    return "neutral"

def make_reply_more_human(reply: str, text: str) -> str:
    """让回复更像真人"""
    preference = check_topic_preference(text)

    if preference == "dismissive":
        dismissive_replies = ["哦", "这样啊", "不太清楚", "不关心这个", "没兴趣"]
        if random.random() < 0.5:
            return random.choice(dismissive_replies)

    if preference == "enthusiastic":
        reply = add_filler_word(reply)
        if should_send_emoji():
            reply += " " + random.choice(EMOJI_PACK)

    if random.random() < 0.15:
        reply = add_filler_word(reply)

    if should_send_emoji() and "[表情包" not in reply:
        reply += " " + random.choice(EMOJI_PACK)

    return reply

# ✅==================== 这里用 extra_body 传联网参数 ====================
def get_llm():
    return ChatOpenAI(
        api_key=QWEN_API_KEY,
        base_url=BASE_URL,
        model=MODEL_NAME,
        temperature=0.7,
        extra_body={"enable_search": AI_ENABLE_SEARCH}
    )

def get_chain():
    return prompt | get_llm() | StrOutputParser()

chat_bot = RunnableWithMessageHistory(
    get_chain(),
    get_session_history,
    input_messages_key="input",
    history_messages_key="history"
)

user_last_image = {}
chat_log_handler = on_message(priority=1, block=False)

# -------------------------- 工具函数 --------------------------
def write_log_to_chat(record_type, content, user_id="系统", user_name="系统"):
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_data = {
            "time": current_time,
            "user_id": str(user_id),
            "user_name": user_name,
            "message": f"【{record_type}】{content}"
        }
        logs = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f) or []
            except:
                logs = []
        logs.append(log_data)
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写日志失败：{e}")

def clean_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"#{1,6}\s?", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"^[-\*+]\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"-{3,}", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_text_and_image(event: MessageEvent):
    text = ""
    image_url = None
    for seg in event.message:
        if seg.type == "text":
            text += seg.data.get("text", "")
        elif seg.type == "image":
            image_url = seg.data.get("url", "")
    return text.strip(), image_url

# -------------------------- 识图功能 --------------------------
async def ai_answer_image(text: str, image_url: str):
    try:
        headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "qwen-vl-max",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": text if text else "精准描述图片内容"}
                ]
            }],
            "temperature": 0.7,
            "stream": False
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=50)) as session:
            async with session.post(f"{BASE_URL}/chat/completions", headers=headers, json=data) as resp:
                if resp.status == 200:
                    res = await resp.json()
                    return clean_output(res["choices"][0]["message"]["content"])
                else:
                    return "识别失败"
    except Exception as e:
        logger.error(f"识图错误：{e}")
        return "看图失败"

# -------------------------- 主逻辑 --------------------------
@chat_log_handler.handle()
async def handle_chat(bot: Bot, event: MessageEvent):
    if str(event.self_id) == str(event.user_id):
        return

    user_id = str(event.user_id)
    is_group = hasattr(event, "group_id")
    text, img_url = extract_text_and_image(event)

    # 保存图片供后续使用
    if img_url:
        user_last_image[user_id] = img_url
        return

    # 群聊没有被@就不回复（除非主动接话）
    if is_group and not event.is_tome():
        # 小概率主动接话
        if random.random() < AUTO_CHAT_PROBABILITY:
            if any(kw in text for kw in AUTO_CHAT_KEYWORDS):
                await asyncio.sleep(random.uniform(1, 5))
                auto_replies = ["确实", "哈哈", "笑死", "真的假的", "666", "牛逼"]
                await bot.send(event, random.choice(auto_replies))
        return

    # 主人特殊回复
    if user_id == str(MASTER_QQ):
        if TRIGGER_KEYWORD in text:
            await bot.send(event, MASTER_REPLY_CONTENT)
            return
        if AAA in text:
            await bot.send(event, BBB)
            return

    # 图片 + 文字的组合
    if text and user_id in user_last_image:
        last_img = user_last_image[user_id]
        del user_last_image[user_id]
        reply = await ai_answer_image(text, last_img)
        await asyncio.sleep(random.uniform(1, 3))
        await bot.send(event, reply)
        write_log_to_chat("AI 识图", f"问题：{text} | 回复：{reply}", user_id)
        return

    # 文字回复
    if text:
        # 检查是否在睡觉时间
        if not is_active_time():
            sleep_replies = ["zzz...", "好困...明天再说吧", "[表情包：睡觉]", "睡了晚安"]
            await bot.send(event, random.choice(sleep_replies))
            return

        # 模拟思考/打字延迟

        delay = get_reply_delay(text)
        await asyncio.sleep(delay)

        try:
            logger.info(f"[AI 模式] 联网状态：{AI_ENABLE_SEARCH}")
            reply = chat_bot.invoke(
                {"input": text},
                config={"configurable": {"session_id": user_id}}
            )
            reply = clean_output(reply)
            # 让回复更像真人
            reply = make_reply_more_human(reply, text)
        except Exception as e:
            logger.error(f"聊天错误：{e}")
            reply = "我出错啦~"

        await bot.send(event, reply)
        write_log_to_chat("AI 对话", f"问题：{text} | 回复：{reply}", user_id)