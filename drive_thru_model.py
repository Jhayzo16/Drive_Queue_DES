from __future__ import annotations

from dataclasses import dataclass, field
import random
from statistics import mean
from typing import Dict, List, Optional

import simpy


@dataclass
class SimulationConfig:
    duration_minutes: int = 1440
    arrival_rate_per_hour: float = 12.0
    peak_multiplier: float = 2.0
    peak_start_minute: int = 660
    peak_end_minute: int = 840
    order_stations: int = 1
    payment_windows: int = 1
    pickup_windows: int = 1
    lane_capacity: int = 10
    seed: int = 42


@dataclass
class Event:
    time: float
    vehicle_id: int
    event_type: str
    message: str
    stage: str
    queue_length: int
    active_vehicles: Dict[int, str] = field(default_factory=dict)


@dataclass
class VehicleRecord:
    vehicle_id: int
    arrival_time: float
    departure_time: Optional[float] = None
    rejected: bool = False
    waits: Dict[str, float] = field(default_factory=dict)
    services: Dict[str, float] = field(default_factory=dict)

    @property
    def total_time(self) -> float:
        if self.departure_time is None:
            return 0.0
        return self.departure_time - self.arrival_time


@dataclass
class SimulationResult:
    config: SimulationConfig
    events: List[Event]
    vehicles: List[VehicleRecord]
    summary: Dict[str, float | int | str]
    stage_waits: Dict[str, List[float]]
    utilization: Dict[str, float]


class DriveThruSimulation:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.random = random.Random(config.seed)
        self.env = simpy.Environment()
        self.order = simpy.Resource(self.env, capacity=config.order_stations)
        self.payment = simpy.Resource(self.env, capacity=config.payment_windows)
        self.pickup = simpy.Resource(self.env, capacity=config.pickup_windows)
        self.events: List[Event] = []
        self.vehicles: List[VehicleRecord] = []
        self.active: Dict[int, str] = {}
        self.in_system = 0
        self.rejected_count = 0
        self.busy_time = {"order": 0.0, "payment": 0.0, "pickup": 0.0}

    def run(self) -> SimulationResult:
        self.env.process(self._arrival_process())
        self.env.run(until=self.config.duration_minutes)
        return self._result()

    def _arrival_rate(self) -> float:
        if self.config.peak_start_minute <= self.env.now < self.config.peak_end_minute:
            return self.config.arrival_rate_per_hour * self.config.peak_multiplier
        return self.config.arrival_rate_per_hour

    def _arrival_process(self):
        vehicle_id = 1
        while self.env.now < self.config.duration_minutes:
            hourly_rate = max(self._arrival_rate(), 0.01)
            interarrival = self.random.expovariate(hourly_rate / 60.0)
            yield self.env.timeout(interarrival)
            if self.env.now >= self.config.duration_minutes:
                break

            if self.in_system >= self.config.lane_capacity:
                record = VehicleRecord(vehicle_id, self.env.now, rejected=True)
                self.vehicles.append(record)
                self.rejected_count += 1
                self._log(
                    vehicle_id,
                    "congestion",
                    "Lane full: vehicle could not enter the drive-thru.",
                    "rejected",
                )
            else:
                self.in_system += 1
                record = VehicleRecord(vehicle_id, self.env.now)
                self.vehicles.append(record)
                self.active[vehicle_id] = "queue"
                self._log(vehicle_id, "arrival", "Vehicle arrived and joined FIFO queue.", "queue")
                self.env.process(self._vehicle_flow(record))

            vehicle_id += 1

    def _vehicle_flow(self, record: VehicleRecord):
        yield from self._use_resource(record, "order", self.order, 1.0, 3.0)
        yield from self._use_resource(record, "payment", self.payment, 0.5, 1.0)
        yield from self._use_resource(record, "pickup", self.pickup, 1.0, 2.0)

        record.departure_time = self.env.now
        self.in_system -= 1
        self.active.pop(record.vehicle_id, None)
        self._log(
            record.vehicle_id,
            "departure",
            f"Vehicle departed after {record.total_time:.1f} minutes in system.",
            "departed",
        )

    def _use_resource(
        self,
        record: VehicleRecord,
        stage: str,
        resource: simpy.Resource,
        service_min: float,
        service_max: float,
    ):
        self.active[record.vehicle_id] = f"waiting_{stage}"
        self._log(record.vehicle_id, f"{stage}_queue", f"Vehicle waiting for {stage}.", f"waiting_{stage}")
        requested_at = self.env.now

        with resource.request() as request:
            yield request
            wait = self.env.now - requested_at
            record.waits[stage] = wait
            self.active[record.vehicle_id] = stage
            self._log(
                record.vehicle_id,
                f"{stage}_start",
                f"{stage.title()} started after {wait:.1f} minutes of waiting.",
                stage,
            )
            service_time = self.random.uniform(service_min, service_max)
            record.services[stage] = service_time
            self.busy_time[stage] += service_time
            yield self.env.timeout(service_time)
            self._log(
                record.vehicle_id,
                f"{stage}_end",
                f"{stage.title()} completed in {service_time:.1f} minutes.",
                stage,
            )

    def _log(self, vehicle_id: int, event_type: str, message: str, stage: str):
        self.events.append(
            Event(
                time=self.env.now,
                vehicle_id=vehicle_id,
                event_type=event_type,
                message=message,
                stage=stage,
                queue_length=self.in_system,
                active_vehicles=dict(self.active),
            )
        )

    def _result(self) -> SimulationResult:
        completed = [v for v in self.vehicles if v.departure_time is not None and not v.rejected]
        accepted = [v for v in self.vehicles if not v.rejected]
        stage_waits = {
            "order": [v.waits.get("order", 0.0) for v in completed],
            "payment": [v.waits.get("payment", 0.0) for v in completed],
            "pickup": [v.waits.get("pickup", 0.0) for v in completed],
        }
        utilization = {
            "order": self.busy_time["order"] / (self.config.duration_minutes * self.config.order_stations),
            "payment": self.busy_time["payment"] / (self.config.duration_minutes * self.config.payment_windows),
            "pickup": self.busy_time["pickup"] / (self.config.duration_minutes * self.config.pickup_windows),
        }
        avg_stage_wait = {
            stage: mean(values) if values else 0.0 for stage, values in stage_waits.items()
        }
        bottleneck = max(avg_stage_wait, key=avg_stage_wait.get) if completed else "none"
        wait_values = [sum(v.waits.values()) for v in completed]

        summary: Dict[str, float | int | str] = {
            "vehicles_generated": len(self.vehicles),
            "vehicles_served": len(completed),
            "vehicles_rejected": self.rejected_count,
            "throughput_per_hour": (len(completed) / self.config.duration_minutes) * 60.0,
            "average_queue_wait": mean(wait_values) if wait_values else 0.0,
            "average_system_time": mean([v.total_time for v in completed]) if completed else 0.0,
            "max_system_time": max([v.total_time for v in completed], default=0.0),
            "bottleneck": bottleneck,
            "acceptance_rate": (len(accepted) / len(self.vehicles) * 100.0) if self.vehicles else 0.0,
        }
        return SimulationResult(
            config=self.config,
            events=self.events,
            vehicles=self.vehicles,
            summary=summary,
            stage_waits=stage_waits,
            utilization=utilization,
        )


def run_simulation(config: SimulationConfig) -> SimulationResult:
    return DriveThruSimulation(config).run()
