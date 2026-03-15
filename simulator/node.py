from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple
import math
import random


@dataclass
class Node:
    id: str
    name: str
    capacity: int = 10
    mean_processing_time: float = 0.05
    std_processing_time: float = 0.01
    failure_rate: float = 0.0
    hit_rate: float = 0.0
    timeout: Optional[float] = None
    processing_profiles: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    fan_out: bool = False    # if True, dispatches to ALL outgoing edges simultaneously

    _active: int = field(default=0, init=False, repr=False)
    _queue: Deque = field(default_factory=deque, init=False, repr=False)
    _is_down: bool = field(default=False, init=False, repr=False)

    @property
    def is_down(self) -> bool:
        return self._is_down

    def go_down(self) -> None:
        self._is_down = True

    def come_up(self) -> None:
        self._is_down = False

    @property
    def active_requests(self) -> int:
        return self._active

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def utilization(self) -> float:
        return self._active / self.capacity if self.capacity > 0 else 0.0

    def is_at_capacity(self) -> bool:
        return self._active >= self.capacity

    def accept(self, request) -> bool:
        if not self.is_at_capacity():
            self._active += 1
            return True
        self._queue.append(request)
        return False

    def release(self):
        self._active -= 1
        if not self._is_down and self._queue:
            next_req = self._queue.popleft()
            self._active += 1
            return next_req
        return None

    def drain_to_capacity(self) -> list:
        promoted = []
        while not self.is_at_capacity() and self._queue:
            req = self._queue.popleft()
            self._active += 1
            promoted.append(req)
        return promoted

    def sample_processing_time(self, request_type: str = "") -> float:
        if request_type in self.processing_profiles:
            mean, std = self.processing_profiles[request_type]
        else:
            mean, std = self.mean_processing_time, self.std_processing_time

        if std == 0.0 or mean <= 0.0:
            return max(0.001, mean)

        # Log-normal parameterisation: derive mu/sigma from desired mean and std
        # so the UI inputs retain their intuitive meaning.
        # For X ~ LogNormal(mu, sigma):
        #   E[X]   = exp(mu + sigma²/2)  =>  mu    = ln(mean) - sigma²/2
        #   Var[X] = (exp(sigma²) - 1) * exp(2*mu + sigma²)  =>  sigma² = ln(1 + (std/mean)²)
        sigma2 = math.log1p((std / mean) ** 2)
        mu = math.log(mean) - sigma2 / 2
        return max(0.001, random.lognormvariate(mu, math.sqrt(sigma2)))

    def remove_from_queue(self, request) -> bool:
        try:
            self._queue.remove(request)
            return True
        except ValueError:
            return False

    def should_fail(self) -> bool:
        return random.random() < self.failure_rate

    def is_cache_hit(self) -> bool:
        return self.hit_rate > 0.0 and random.random() < self.hit_rate

    def reset(self):
        self._active = 0
        self._queue.clear()
        self._is_down = False

    def __repr__(self) -> str:
        return f"Node(id={self.id!r}, active={self._active}/{self.capacity}, queued={self.queue_size})"
