# config/algorithm_config.py
"""
算法配置参数

管理NSGA-II和深度强化学习算法的参数
"""

from typing import Dict, Any


class AlgorithmConfig:
    """
    算法配置类
    """
    
    # NSGA-II算法参数
    NSGA2_CONFIG = {
        "population_size": 100,  # 种群大小
        "generations": 50,  # 进化代数
        "crossover_prob": 0.8,  # 交叉概率
        "mutation_prob": 0.2,  # 变异概率
        "mutation_indpb": 0.1  # 个体变异概率
    }
    
    # 深度强化学习算法参数
    DRL_CONFIG = {
        "episodes": 1000,  # 训练轮数
        "batch_size": 32,  # 批次大小
        "gamma": 0.95,  # 折扣因子
        "epsilon": 1.0,  # 初始探索率
        "epsilon_min": 0.01,  # 最小探索率
        "epsilon_decay": 0.995,  # 探索率衰减
        "learning_rate": 0.001,  # 学习率
        "memory_size": 2000  # 经验回放缓冲区大小
    }
    
    # 混合算法参数
    HYBRID_CONFIG = {
        "nsga2_weight": 0.5,  # NSGA-II解的权重
        "drl_weight": 0.5  # DRL解的权重
    }
    
    # 算法选择
    DEFAULT_ALGORITHM = "nsga2"  # 默认算法
    
    @classmethod
    def get_config(cls, algorithm: str) -> Dict[str, Any]:
        if algorithm == "nsga2":
            return cls.NSGA2_CONFIG
        elif algorithm == "drl":
            return cls.DRL_CONFIG
        elif algorithm == "hybrid":
            return cls.HYBRID_CONFIG
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")
    
    @classmethod
    def update_config(cls, algorithm: str, **kwargs):
        config = cls.get_config(algorithm)
        config.update(kwargs)
    
    @classmethod
    def get_default_algorithm(cls) -> str:
        return cls.DEFAULT_ALGORITHM
    
    @classmethod
    def set_default_algorithm(cls, algorithm: str):
        if algorithm not in ["nsga2", "drl", "hybrid"]:
            raise ValueError(f"Unknown algorithm: {algorithm}")
        cls.DEFAULT_ALGORITHM = algorithm


algorithm_config = AlgorithmConfig()
