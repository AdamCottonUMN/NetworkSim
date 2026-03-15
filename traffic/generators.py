from __future__ import annotations
import random
from typing import List

from simulator.engine import Event, EventType
from simulator.request import Request


def poisson_arrivals(
    rate: float,
    duration: float,
    entry_node_id: str,
    request_type: str = "http",
    seed: int | None = None,
) -> List[Event]:
    """
    Generate request arrival events using a Poisson process.

    Parameters
    ----------
    rate          : average requests per second
    duration      : simulation window in seconds
    entry_node_id : ID of the first node requests should arrive at
    request_type  : label attached to each Request
    seed          : optional RNG seed for reproducibility

    Returns
    -------
    List of Event objects (already sorted by time) ready to be pushed into
    the engine's heap.
    """
    rng = random.Random(seed)
    events: List[Event] = []
    time = 0.0

    while True:
        inter_arrival = rng.expovariate(rate)  # Exp(rate) inter-arrival times
        time += inter_arrival
        if time >= duration:
            break
        req = Request(request_type=request_type, created_at=time)
        events.append(
            Event(
                time=time,
                event_type=EventType.REQUEST_ARRIVE,
                request=req,
                node_id=entry_node_id,
            )
        )

    return events  # already sorted because we generate chronologically


def mixed_arrivals(
    rate: float,
    duration: float,
    entry_node_id: str,
    mix: dict,
    seed: int | None = None,
) -> List[Event]:
    rng = random.Random(seed)
    types = list(mix.keys())
    weights = [mix[t] for t in types]
    events: List[Event] = []
    time = 0.0

    while True:
        inter_arrival = rng.expovariate(rate)
        time += inter_arrival
        if time >= duration:
            break
        rtype = rng.choices(types, weights=weights)[0]
        req = Request(request_type=rtype, created_at=time)
        events.append(
            Event(
                time=time,
                event_type=EventType.REQUEST_ARRIVE,
                request=req,
                node_id=entry_node_id,
            )
        )

    return events


def burst_arrivals(
    rate: float,
    duration: float,
    entry_node_id: str,
    burst_start: float,
    burst_end: float,
    burst_multiplier: float = 5.0,
    request_type: str = "http",
    seed: int | None = None,
) -> List[Event]:
    """
    Poisson traffic with a temporary traffic spike between burst_start and burst_end.

    Outside the burst window the rate is `rate`; inside it is `rate * burst_multiplier`.
    """
    rng = random.Random(seed)
    events: List[Event] = []
    time = 0.0

    while True:
        current_rate = rate * burst_multiplier if burst_start <= time <= burst_end else rate
        inter_arrival = rng.expovariate(current_rate)
        time += inter_arrival
        if time >= duration:
            break
        req = Request(request_type=request_type, created_at=time)
        events.append(
            Event(
                time=time,
                event_type=EventType.REQUEST_ARRIVE,
                request=req,
                node_id=entry_node_id,
            )
        )

    return events
