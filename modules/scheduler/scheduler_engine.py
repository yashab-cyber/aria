"""
A.R.I.A. Scheduler Engine — Autonomous task scheduling with persistence.

Supports three trigger modes:
  - cron:     "every Monday at 9am", "nightly at midnight"
  - interval: "every 30 minutes", "every 2 hours"
  - one_shot: "in 15 minutes", "at 3pm today"

Jobs are persisted to SQLite so they survive server restarts.
Results can be optionally routed through the notifications module.
"""

import asyncio
import uuid
import json
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from core.tool_registry import aria_tool
from config import config
from rich.console import Console

console = Console()


class _JobStore:
    """Lightweight SQLite store for scheduled job metadata."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    task_prompt TEXT NOT NULL, trigger TEXT NOT NULL,
                    trigger_args TEXT NOT NULL, notify_channel TEXT,
                    created_at TEXT NOT NULL, paused INTEGER DEFAULT 0,
                    last_run TEXT, run_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, ran_at TEXT NOT NULL,
                    result TEXT, success INTEGER DEFAULT 1,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                )
            """)
            conn.commit()

    def save_job(self, job: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO jobs (job_id,name,task_prompt,trigger,trigger_args,notify_channel,created_at,paused,last_run,run_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (job["job_id"], job["name"], job["task_prompt"], job["trigger"],
                 json.dumps(job["trigger_args"]), job.get("notify_channel"),
                 job["created_at"], int(job.get("paused", False)),
                 job.get("last_run"), job.get("run_count", 0)),
            )
            conn.commit()

    def remove_job(self, job_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            return c.rowcount > 0

    def get_all_jobs(self) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()]

    def get_job(self, job_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def update_field(self, job_id: str, field: str, value):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE jobs SET {field} = ? WHERE job_id = ?", (value, job_id))
            conn.commit()

    def record_run(self, job_id: str, result: str, success: bool = True):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO job_history (job_id,ran_at,result,success) VALUES (?,?,?,?)",
                         (job_id, now, result[:2000], int(success)))
            conn.execute("UPDATE jobs SET last_run=?, run_count=run_count+1 WHERE job_id=?", (now, job_id))
            conn.commit()

    def get_history(self, job_id: str, limit: int = 10) -> List[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM job_history WHERE job_id=? ORDER BY id DESC LIMIT ?", (job_id, limit)
            ).fetchall()]


class SchedulerEngine:
    def __init__(self):
        self._store = _JobStore(config.scheduler_db_path)
        self._tasks: Dict[str, asyncio.Task] = {}
        self._scheduler = None
        self._use_apscheduler = False
        self._started = False

    async def start(self):
        if self._started:
            return
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
            self._scheduler.start()
            self._use_apscheduler = True
            console.print("[bold green]⏰ Scheduler started (APScheduler)[/bold green]")
        except ImportError:
            console.print("[bold yellow]⏰ Scheduler started (asyncio fallback)[/bold yellow]")
        self._started = True
        persisted = self._store.get_all_jobs()
        restored = 0
        for j in persisted:
            if not j.get("paused"):
                try:
                    ta = json.loads(j["trigger_args"]) if isinstance(j["trigger_args"], str) else j["trigger_args"]
                    await self._register(j["job_id"], j["task_prompt"], j["trigger"], ta, j.get("notify_channel"))
                    restored += 1
                except Exception as e:
                    console.print(f"[yellow]Could not restore job {j['job_id']}: {e}[/yellow]")
        if restored:
            console.print(f"[cyan]Restored {restored} job(s) from database.[/cyan]")

    async def shutdown(self):
        if self._scheduler and self._use_apscheduler:
            self._scheduler.shutdown(wait=False)
        for t in self._tasks.values():
            t.cancel()
        self._tasks.clear()
        self._started = False
        console.print("[cyan]Scheduler shut down.[/cyan]")

    async def _register(self, job_id, prompt, trigger, args, notify=None):
        async def cb():
            await self._run_job(job_id, prompt, notify)
        if self._use_apscheduler and self._scheduler:
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger
            from apscheduler.triggers.date import DateTrigger
            if trigger == "cron":
                t = CronTrigger(**args)
            elif trigger == "interval":
                t = IntervalTrigger(**args)
            else:
                rd = args.get("run_date")
                if isinstance(rd, str):
                    rd = datetime.fromisoformat(rd)
                t = DateTrigger(run_date=rd)
            self._scheduler.add_job(cb, trigger=t, id=job_id, replace_existing=True)
        else:
            self._tasks[job_id] = asyncio.create_task(self._asyncio_loop(job_id, prompt, trigger, args, notify))

    async def _asyncio_loop(self, job_id, prompt, trigger, args, notify):
        try:
            if trigger == "one_shot":
                rd = args.get("run_date", "")
                if rd:
                    delay = (datetime.fromisoformat(rd) - datetime.utcnow()).total_seconds()
                else:
                    delay = args.get("delay_seconds", 60)
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._run_job(job_id, prompt, notify)
                self._store.remove_job(job_id)
                self._tasks.pop(job_id, None)
            elif trigger == "interval":
                secs = args.get("seconds", 0) + args.get("minutes", 0) * 60 + args.get("hours", 0) * 3600
                if secs <= 0:
                    secs = 3600
                while True:
                    await asyncio.sleep(secs)
                    await self._run_job(job_id, prompt, notify)
            elif trigger == "cron":
                hour, minute = int(args.get("hour", 0)), int(args.get("minute", 0))
                dow = args.get("day_of_week")
                while True:
                    now = datetime.utcnow()
                    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if nxt <= now:
                        nxt += timedelta(days=1)
                    if dow:
                        names = ["mon","tue","wed","thu","fri","sat","sun"]
                        targets = []
                        for p in str(dow).split(","):
                            p = p.strip().lower()
                            if p in names:
                                targets.append(names.index(p))
                            elif p.isdigit():
                                targets.append(int(p))
                        if targets:
                            while nxt.weekday() not in targets:
                                nxt += timedelta(days=1)
                    d = (nxt - datetime.utcnow()).total_seconds()
                    if d > 0:
                        await asyncio.sleep(d)
                    await self._run_job(job_id, prompt, notify)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            console.print(f"[red]Job {job_id} error: {e}[/red]")

    async def _run_job(self, job_id, prompt, notify):
        console.print(f"\n[bold magenta]⏰ Job firing: {job_id}[/bold magenta]")
        result, success = "", True
        try:
            from core.aria import orchestrator
            async for chunk in orchestrator.process(prompt):
                result += chunk
        except Exception as e:
            result, success = f"Error: {e}", False
            console.print(f"[red]Job {job_id} failed: {e}[/red]")
        self._store.record_run(job_id, result, success)
        if notify:
            try:
                from modules.notifications.notification_manager import notifier
                job = self._store.get_job(job_id)
                name = job["name"] if job else job_id
                await notifier.send(notify, f"⏰ Task Complete: {name}\n\n{result[:1500]}")
            except Exception as e:
                console.print(f"[yellow]Notification failed: {e}[/yellow]")

    # ── ARIA Tools ──

    @aria_tool(name="schedule_task", description="Schedule an autonomous task. trigger: 'cron','interval','one_shot'. trigger_args JSON: cron={hour,minute,day_of_week}, interval={seconds,minutes,hours}, one_shot={delay_seconds or run_date}. notify_channel: slack/telegram/discord/email/whatsapp (optional).")
    async def schedule_task(self, name: str, task_prompt: str, trigger: str = "one_shot", trigger_args: str = "{}", notify_channel: str = "") -> str:
        try:
            jid = f"aria_{uuid.uuid4().hex[:8]}"
            pa = json.loads(trigger_args) if isinstance(trigger_args, str) else trigger_args
            nc = notify_channel if notify_channel else None
            if trigger not in ("cron", "interval", "one_shot"):
                return f"Invalid trigger: '{trigger}'. Use cron/interval/one_shot."
            job = {"job_id": jid, "name": name, "task_prompt": task_prompt, "trigger": trigger,
                   "trigger_args": pa, "notify_channel": nc, "created_at": datetime.utcnow().isoformat(),
                   "paused": False, "last_run": None, "run_count": 0}
            self._store.save_job(job)
            await self._register(jid, task_prompt, trigger, pa, nc)
            ns = f" → notify {nc}" if nc else ""
            return f"Scheduled '{name}' (ID: {jid}){ns}."
        except Exception as e:
            return f"Failed to schedule: {e}"

    @aria_tool(name="list_scheduled_tasks", description="Lists all scheduled tasks with status, trigger, and last run.")
    async def list_scheduled_tasks(self) -> str:
        jobs = self._store.get_all_jobs()
        if not jobs:
            return "No scheduled tasks."
        lines = [f"📋 {len(jobs)} Scheduled Task(s):\n"]
        for j in jobs:
            st = "⏸️ PAUSED" if j.get("paused") else "▶️ ACTIVE"
            ta = json.loads(j["trigger_args"]) if isinstance(j["trigger_args"], str) else j["trigger_args"]
            ts = f"{j['trigger']}({', '.join(f'{k}={v}' for k,v in ta.items())})"
            lines.append(f"  {st} [{j['job_id']}] \"{j['name']}\" | {ts} | Runs: {j.get('run_count',0)}")
        return "\n".join(lines)

    @aria_tool(name="cancel_scheduled_task", description="Cancels a scheduled task by job ID.")
    async def cancel_scheduled_task(self, job_id: str) -> str:
        if self._use_apscheduler and self._scheduler:
            try: self._scheduler.remove_job(job_id)
            except: pass
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            del self._tasks[job_id]
        return f"Cancelled {job_id}." if self._store.remove_job(job_id) else f"Job not found: {job_id}"

    @aria_tool(name="pause_scheduled_task", description="Pauses a scheduled task (keeps it in DB).")
    async def pause_scheduled_task(self, job_id: str) -> str:
        job = self._store.get_job(job_id)
        if not job:
            return f"Job not found: {job_id}"
        if self._use_apscheduler and self._scheduler:
            try: self._scheduler.pause_job(job_id)
            except: pass
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            del self._tasks[job_id]
        self._store.update_field(job_id, "paused", 1)
        return f"Paused: {job_id}"

    @aria_tool(name="resume_scheduled_task", description="Resumes a paused scheduled task.")
    async def resume_scheduled_task(self, job_id: str) -> str:
        job = self._store.get_job(job_id)
        if not job:
            return f"Job not found: {job_id}"
        if not job.get("paused"):
            return f"Job {job_id} is not paused."
        ta = json.loads(job["trigger_args"]) if isinstance(job["trigger_args"], str) else job["trigger_args"]
        await self._register(job_id, job["task_prompt"], job["trigger"], ta, job.get("notify_channel"))
        self._store.update_field(job_id, "paused", 0)
        return f"Resumed: {job_id}"

    def get_jobs_for_api(self) -> List[dict]:
        jobs = self._store.get_all_jobs()
        for j in jobs:
            if isinstance(j.get("trigger_args"), str):
                j["trigger_args"] = json.loads(j["trigger_args"])
        return jobs


scheduler = SchedulerEngine()
