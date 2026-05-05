"""Cron Scheduler — natural language scheduled tasks with platform delivery.

Inspired by Hermes Agent cron: "每天早上8点汇总昨日工作" → scheduled task.
Runs in-process asyncio loop. Tasks survive restart via JSON persistence.

Commands: /cron add <task>  /cron list  /cron remove <id>  /cron test <id>
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from loguru import logger

CRON_FILE = Path(".livingtree/cron_jobs.json")


@dataclass
class CronJob:
    id: str
    description: str
    schedule: str  # "daily 08:00", "hourly", "weekly mon 09:00" or cron expression
    prompt: str
    platform: str = "cli"  # cli, telegram, discord
    enabled: bool = True
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description,
            "schedule": self.schedule, "prompt": self.prompt,
            "platform": self.platform, "enabled": self.enabled,
            "last_run": self.last_run, "next_run": self.next_run,
            "run_count": self.run_count, "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CronJob:
        return cls(**d)

    def compute_next_run(self) -> float:
        now = datetime.now()
        s = self.schedule.lower().strip()
        if s.startswith("daily"):
            parts = s.split()
            hour, minute = 8, 0
            if len(parts) > 1:
                try:
                    h, m = parts[1].split(":")
                    hour, minute = int(h), int(m)
                except ValueError:
                    pass
            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time.timestamp()
        elif s.startswith("hourly"):
            next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return next_time.timestamp()
        elif s.startswith("weekly"):
            day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            parts = s.split()
            target_day = 0
            hour, minute = 9, 0
            for p in parts[1:]:
                if p in day_map:
                    target_day = day_map[p]
                elif ":" in p:
                    try:
                        h, m = p.split(":")
                        hour, minute = int(h), int(m)
                    except ValueError:
                        pass
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
            return next_time.timestamp()
        else:
            return (now + timedelta(hours=1)).timestamp()

    def due(self) -> bool:
        return time.time() >= self.next_run


class CronScheduler:
    """In-process cron scheduler with persistent jobs."""

    def __init__(self):
        self._jobs: dict[str, CronJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._callback: Callable | None = None
        self._load()

    def set_callback(self, cb: Callable):
        """Set the function called when a job is due. Signature: async def cb(job: CronJob)."""
        self._callback = cb

    def add(self, description: str, schedule: str, prompt: str, platform: str = "cli") -> CronJob:
        job = CronJob(
            id=f"cron-{len(self._jobs)+1}",
            description=description,
            schedule=schedule,
            prompt=prompt,
            platform=platform,
        )
        job.next_run = job.compute_next_run()
        self._jobs[job.id] = job
        self._save()
        logger.info(f"Cron added: {job.id} — {description}")
        return job

    def remove(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def list(self) -> list[CronJob]:
        return sorted(self._jobs.values(), key=lambda j: j.next_run)

    def get(self, job_id: str) -> CronJob | None:
        return self._jobs.get(job_id)

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Cron started: {len(self._jobs)} jobs")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            now = time.time()
            for job in list(self._jobs.values()):
                if job.enabled and job.due():
                    if self._callback:
                        from ..observability.system_monitor import get_monitor
                        if get_monitor().can_run_task(f"cron:{job.id}", heavy=False):
                            try:
                                await self._callback(job)
                            except Exception as e:
                                logger.error(f"Cron job {job.id}: {e}")
                    job.last_run = now
                    job.run_count += 1
                    job.next_run = job.compute_next_run()
                    self._save()
            await asyncio.sleep(30)

    def _save(self):
        from ..core.async_disk import save_json
        data = [j.to_dict() for j in self._jobs.values()]
        save_json(CRON_FILE, data)

    def _load(self):
        try:
            if CRON_FILE.exists():
                data = json.loads(CRON_FILE.read_text())
                for d in data:
                    self._jobs[d["id"]] = CronJob.from_dict(d)
                logger.info(f"Cron loaded: {len(self._jobs)} jobs")
        except Exception:
            pass


# ═══ Global ═══

_scheduler: CronScheduler | None = None


def get_scheduler() -> CronScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = CronScheduler()
    return _scheduler
