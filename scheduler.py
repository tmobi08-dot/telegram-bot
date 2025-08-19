from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

scheduler = AsyncIOScheduler(timezone=pytz.utc)

def schedule_task(func, **kwargs):
    scheduler.add_job(func, **kwargs)

def start_scheduler():
    scheduler.start()
