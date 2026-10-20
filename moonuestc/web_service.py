"""One school-request worker for dashboard jobs and daily scheduling."""
import threading
import time

from .errors import ToolError
from .diagnostics import error_details
from .policy import clock_minutes,now
from .runner import account_key,run_account
from .state import State,execution_lock
from .vault import EncryptedTransport
from .web_errors import WebError


class WebWorker:
    def __init__(self,store,runner=None,gap_seconds=20):
        self.store=store
        self.runner=runner or run_account
        self.gap_seconds=max(20,gap_seconds)
        self.stop_event=threading.Event()
        self.thread=None
        self.next_job_at=0

    def schedule_once(self):
        instant=now()
        minute=instant.hour*60+instant.minute
        day=instant.date().isoformat()
        for row in self.store.automatic_accounts():
            if minute<clock_minutes(row['run_at']): continue
            try:
                payload=self.store.vault.open(row['payload'],'account:'+row['id'])
                state=State(self.store.directory)
                try: ready=state.ready(account_key(payload))
                finally: state.close()
                if not ready: continue
                self.store.enqueue({'id':row['owner_id'],'role':'admin'},row['id'],'checkin','schedule',day)
            except (WebError,ToolError):
                continue

    def run_one(self):
        job=self.store.claim_job()
        if not job: return False
        payload=None
        try:
            self.store.record_job_event(job,'run_started',{})
            if job['business_date']!=now().date().isoformat():
                raise ToolError('job_expired','worker')
            payload=self.store.job_payload(job)
            with execution_lock(self.store.directory):
                state=State(self.store.directory)
                try:
                    result=self.runner(payload,job['mode'],state,self.store.directory,
                        emit=lambda event,**values:self.store.record_job_event(job,event,values,payload),
                        run_id=job['id'],
                        transport_factory=lambda ua,path:EncryptedTransport(ua,path,self.store))
                finally: state.close()
        except ToolError as error:
            result={'result':'error',**error_details(error,payload)}
            self.store.record_job_event(job,'run_error',{'error':error},payload)
        except WebError as error:
            result={'result':'error','reason':error.code,'stage':'worker'}
        except Exception:
            result={'result':'error','reason':'worker_internal_error','stage':'worker'}
        self.store.finish_job(job,result)
        return True

    def start(self):
        if self.thread: return
        self.store.recover_jobs()
        def loop():
            while not self.stop_event.is_set():
                try:
                    self.schedule_once()
                    if time.monotonic()>=self.next_job_at and self.run_one():
                        self.next_job_at=time.monotonic()+self.gap_seconds
                except Exception:
                    # School secrets and raw exception messages never enter web logs.
                    pass
                self.stop_event.wait(1)
        self.thread=threading.Thread(target=loop,name='moon-checkin-worker',daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=3)
