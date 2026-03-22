"""
LLM 文字后处理模块
- polish()       基础润色：去口头禅、修标点，不改内容
- format_smart() 智能整理：结构化为 Markdown 列表
"""

from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _client


def _call(system_prompt: str, text: str) -> str:
    resp = _get_client().chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


_POLISH_PROMPT = """你是一个语音转录后处理助手，风格极度保守。只做以下两件事：
1. 删除口头禅和停顿词（嗯、啊、那个、就是、然后然后、好吧好吧 等），直接删除，不替换
2. 如果说话者中途改口（"不是，我是说…"），保留最终说法，删除被推翻的部分
不解释、不演绎、不补充、不改写，原文说什么就输出什么（去掉口头禅后）。
直接输出整理后的文本，不要任何说明或注释。"""

_SMART_PROMPT = """你是一个语音转录后处理助手，风格极度保守。你的工作是最小化整理：

规则：
1. 删除口头禅和停顿词（嗯、啊、那个、就是、然后然后、好吧好吧 等），直接删除，不替换
2. 处理自我纠正：当说话者中途改口（"不是，我是说…"），保留最终说法，删除被推翻的部分
3. 仅当说话者明确列举了多个点（如"第一…第二…"或"有三件事"），才整理为对应的有序/无序列表；否则输出连续段落
4. 不解释、不演绎、不补充、不改写——原文说什么你就输出什么（去掉口头禅后）
5. 如果原文是问句，输出也必须是问句；如果是陈述，输出也必须是陈述

直接输出整理后的文本，不要任何说明或注释。"""


def polish(text: str) -> str:
    """基础润色：去口头禅、修标点，保留原意。"""
    return _call(_POLISH_PROMPT, text)


def format_smart(text: str) -> str:
    """智能整理：转为结构化 Markdown 列表。"""
    return _call(_SMART_PROMPT, text)
