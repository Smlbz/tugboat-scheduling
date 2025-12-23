# agents/base_agent.py
"""
Agent 抽象基类
所有 Agent 必须继承此类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import logging


class BaseAgent(ABC):
    """智能体基类"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.agent_name)
        self.logger.setLevel(logging.INFO)
    
    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Agent名称"""
        pass
    
    @property
    def agent_type(self) -> str:
        """Agent类型: master / slave"""
        return "slave"
    
    @abstractmethod
    def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理请求的通用接口"""
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {"agent_name": self.agent_name, "status": "healthy"}
