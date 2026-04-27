# config/algorithm_config.py
"""
算法配置参数

管理NSGA-II算法的参数
"""

from typing import Dict, Any


class AlgorithmConfig:
    """
    算法配置类
    """

    # NSGA-II算法参数
    NSGA2_CONFIG = {
        "population_size": 60,  # 种群大小
        "generations": 30,  # 进化代数
        "crossover_prob": 0.8,  # 交叉概率
        "mutation_prob": 0.2,  # 变异概率
        "mutation_indpb": 0.1  # 个体变异概率
    }

    @classmethod
    def get_config(cls, algorithm: str) -> Dict[str, Any]:
        if algorithm == "nsga2":
            return cls.NSGA2_CONFIG
        raise ValueError(f"Unknown algorithm: {algorithm}")

    @classmethod
    def update_config(cls, algorithm: str, **kwargs):
        config = cls.get_config(algorithm)
        config.update(kwargs)
