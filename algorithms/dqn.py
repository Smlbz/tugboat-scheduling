"""
DQN: Deep Q-Network for tug scheduling (table-based, no PyTorch/TensorFlow)

Uses dict-based Q-table and discretized state representation.
"""

import random
import logging
from collections import deque
from typing import List, Dict, Optional, Tuple

from interfaces.schemas import Tug, Job, TugStatus

logger = logging.getLogger("DQN")


class ReplayBuffer:
    """Experience replay buffer with fixed capacity."""

    def __init__(self, capacity: int = 2000):
        self.buffer = deque(maxlen=capacity)

    def push(
        self, state: tuple, action: int, reward: float,
        next_state: tuple, done: bool,
    ):
        """Store a transition."""
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> Tuple[tuple, ...]:
        """Random mini-batch from buffer."""
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        return tuple(zip(*batch))

    def __len__(self) -> int:
        return len(self.buffer)


class DQN:
    """
    Deep Q-Network with table-based Q-function.

    No external ML framework needed -- uses Python dict for Q-table.
    """

    def __init__(self, config: Optional[dict] = None):
        from config.algorithm_config import AlgorithmConfig

        self.config = config or AlgorithmConfig.get_config("drl")
        self.q_table: Dict[tuple, float] = {}  # (state, action) -> Q-value

        self.epsilon = self.config["epsilon"]
        self.epsilon_min = self.config["epsilon_min"]
        self.epsilon_decay = self.config["epsilon_decay"]
        self.gamma = self.config["gamma"]
        self.lr = self.config["learning_rate"]

        self.memory = ReplayBuffer(self.config["memory_size"])
        logger.info(
            "DQN init eps=%.2f gamma=%.2f lr=%.4f memory=%d",
            self.epsilon, self.gamma, self.lr, self.config["memory_size"],
        )

    # ---- state extraction ----

    def _extract_state(self, job: Job, tugs: List[Tug]) -> tuple:
        """
        Build a discretized state tuple from a Job and the current tug pool.

        State features:
          job:  required_horsepower/10000, required_tug_count/5,
                is_high_risk(0/1), priority/10
          tugs: horsepower/10000, fatigue_value/15, today_work_hours/24,
                status==AVAILABLE(0/1)  (mean over pool)
        """
        # job features
        j_hp = job.required_horsepower / 10000.0
        j_cnt = job.required_tug_count / 5.0
        j_risk = 1.0 if job.is_high_risk else 0.0
        j_pri = job.priority / 10.0

        # tug pool mean features
        if tugs:
            t_hp = sum(t.horsepower for t in tugs) / len(tugs) / 10000.0
            t_fat = sum(t.fatigue_value for t in tugs) / len(tugs) / 15.0
            t_hrs = sum(t.today_work_hours for t in tugs) / len(tugs) / 24.0
            t_avail = (
                sum(1.0 for t in tugs if t.status == TugStatus.AVAILABLE)
                / len(tugs)
            )
        else:
            t_hp = t_fat = t_hrs = t_avail = 0.0

        return (
            round(j_hp, 1),
            round(j_cnt, 1),
            round(j_risk, 1),
            round(j_pri, 1),
            round(t_hp, 1),
            round(t_fat, 1),
            round(t_hrs, 1),
            round(t_avail, 1),
        )

    # ---- action selection ----

    def select_action(self, state: tuple, valid_actions: List[int]) -> int:
        """Epsilon-greedy: explore random / exploit best Q."""
        if random.random() < self.epsilon:
            return random.choice(valid_actions)

        qs = [self.q_table.get((state, a), 0.0) for a in valid_actions]
        best_q = max(qs)
        best = [a for a, q in zip(valid_actions, qs) if q == best_q]
        return random.choice(best)

    # ---- training ----

    def train_step(
        self, state: tuple, action: int, reward: float,
        next_state: tuple, done: bool,
    ):
        """Single Q-learning update: Q(s,a) += lr * (target - Q(s,a))."""
        current_q = self.q_table.get((state, action), 0.0)

        if done:
            target = reward
        else:
            max_next_q = max(
                (self.q_table.get((next_state, a), 0.0) for a in range(50)),
                default=0.0,
            )
            target = reward + self.gamma * max_next_q

        self.q_table[(state, action)] = current_q + self.lr * (target - current_q)

    @staticmethod
    def _calc_reward(tug: Tug, job: Job) -> float:
        """
        Reward = horsepower match - fatigue penalty - work-hours penalty.

        Components:
          hp_match (0.6):  1 - |tug.hp - per_tug_hp| / per_tug_hp
          fatigue  (0.25): -tug.fatigue_value / 15
          work_hrs (0.15): -tug.today_work_hours / 24
        """
        per_tug_hp = job.required_horsepower / max(job.required_tug_count, 1)
        if per_tug_hp > 0:
            hp_match = 1.0 - min(
                abs(tug.horsepower - per_tug_hp) / per_tug_hp, 1.0
            )
        else:
            hp_match = 1.0

        fatigue_pen = tug.fatigue_value / 15.0
        work_pen = tug.today_work_hours / 24.0

        return hp_match * 0.6 - fatigue_pen * 0.25 - work_pen * 0.15

    def train(
        self, jobs: List[Job], tugs: List[Tug],
        episodes: Optional[int] = None,
    ):
        """
        Train Q-table over *episodes* episodes.

        Each episode: shuffle jobs, for each job select tug(s) via
        epsilon-greedy, update Q-table with Q-learning rule.
        """
        episodes = episodes or self.config["episodes"]

        for ep in range(episodes):
            total_reward = 0.0
            shuffled = list(jobs)
            random.shuffle(shuffled)
            available = list(tugs)

            for job in shuffled:
                needed = max(job.required_tug_count, 1)
                if len(available) < needed:
                    continue

                for _ in range(needed):
                    state = self._extract_state(job, available)
                    valid = list(range(len(available)))
                    action = self.select_action(state, valid)
                    tug = available[action]

                    reward = self._calc_reward(tug, job)
                    total_reward += reward

                    available.pop(action)

                    next_state = (
                        self._extract_state(job, available)
                        if available
                        else state
                    )
                    done = len(available) < needed

                    self.train_step(state, action, reward, next_state, done)
                    self.memory.push(state, action, reward, next_state, done)

            # decay exploration rate
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

            if (ep + 1) % 100 == 0:
                logger.info(
                    "Ep %d/%d eps=%.3f reward=%.2f qsize=%d",
                    ep + 1, episodes, self.epsilon,
                    total_reward, len(self.q_table),
                )

    # ---- scheduling ----

    def schedule(
        self, jobs: List[Job], tugs: List[Tug],
    ) -> Dict[str, List[str]]:
        """
        Train 50 episodes, then greedy inference.

        Returns {job_id: [tug_id, ...]}.
        """
        n_train = min(50, self.config["episodes"])
        self.train(jobs, tugs, episodes=n_train)
        logger.info(
            "DQN schedule ready (%d eps, %d q-entries)",
            n_train, len(self.q_table),
        )

        result: Dict[str, List[str]] = {}
        available = list(tugs)
        sorted_jobs = sorted(jobs, key=lambda j: j.priority, reverse=True)

        for job in sorted_jobs:
            needed = max(job.required_tug_count, 1)
            if len(available) < needed:
                result[job.id] = []
                continue

            assigned_ids = []
            for _ in range(needed):
                state = self._extract_state(job, available)
                valid = list(range(len(available)))
                qs = [self.q_table.get((state, a), 0.0) for a in valid]
                best_q = max(qs)
                candidates = [
                    available[a] for a, q in zip(valid, qs) if q == best_q
                ]
                chosen = random.choice(candidates)

                assigned_ids.append(chosen.id)
                available = [t for t in available if t.id != chosen.id]

            result[job.id] = assigned_ids

        return result
