"""
LLM API 客户端 (DeepSeek/OpenAI 兼容接口)
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional


class LLMClient:
    """LLM API 封装, 每次创建直接从 environ 读 (绕过 config 模块缓存)"""

    def __init__(self):
        self.logger = logging.getLogger("LLMClient")
        self.client = None
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 300

        # 直接从 environ 读, 每次重新加载 .env
        # config 模块在 import 时冻结, 后续改 .env 不生效
        try:
            from dotenv import load_dotenv
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)
        except ImportError:
            pass

        self._api_key = os.getenv("LLM_API_KEY", "")
        self._model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
        self._base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self._provider = os.getenv("LLM_PROVIDER", "deepseek")

        if not self._api_key:
            self.logger.warning("LLM_API_KEY 未设置, 使用模板降级模式")
            return

        try:
            _old_ssl = os.environ.pop("SSL_CERT_FILE", None)
            import openai

            self.client = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )

            if _old_ssl is not None:
                os.environ["SSL_CERT_FILE"] = _old_ssl

            self.logger.info(f"LLM 客户端初始化成功 (provider={self._provider}, model={self._model})")
        except Exception as e:
            self.logger.warning(f"LLM 客户端初始化失败: {e}, 使用模板降级模式")
            self.client = None

    def chat(self, messages: List[Dict], temperature: float = 0.7,
             max_tokens: int = 1000) -> str:
        """调用 LLM chat 接口, 失败时返回 None"""
        if not self.client:
            return None

        key_data = json.dumps({"msgs": messages, "temp": temperature, "model": self._model}, sort_keys=True, default=str)
        cache_key = hashlib.md5(key_data.encode()).hexdigest()
        import time
        now = time.time()
        if cache_key in self._cache:
            ts, resp = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return resp

        try:
            resp = self.client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            result = resp.choices[0].message.content.strip()
            self._cache[cache_key] = (now, result)
            return result
        except Exception as e:
            self.logger.warning(f"LLM 调用失败: {e}")
            return None
