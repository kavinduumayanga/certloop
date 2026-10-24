from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from app.config import get_settings
from app.database import SessionLocal
from app.models import Batch, DeliveryStatus, Participant, SendRecord
from app.services.delivery import DeliveryManager
from app.services.rendering import RENDER_STYLE_VERSION, render_version_path
from app.services.smtp import DefiniteSendError, TransientSendError, UncertainSendError


def seed(status=DeliveryStatus.PENDING):
    with SessionLocal() as db:
        batch=Batch(sender_email="sender@example.edu",send_confirmed=True,email_subject="Hi {name}",email_body="For {workshop_name}; welcome {name}")
        db.add(batch);db.flush()
        path=Path("data/test-data/dummy.pdf");path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"%PDF-test")
        render_version_path(path.resolve()).write_text(RENDER_STYLE_VERSION,encoding="utf-8")
        p=Participant(batch_id=batch.id,row_number=2,name="Ada",email="ada@example.edu",normalized_email="ada@example.edu",is_valid=True,certificate_path=str(path.resolve()),certificate_revision=batch.certificate_revision,idempotency_key=f"cert-{batch.id}-p",status=status)
        db.add(p);db.commit();return batch.id,p.id


class FakeClient:
    def __init__(self,error=None): self.error=error;self.calls=0;self.closed=False;self.messages=[]
    def send(self,*args):
        self.calls+=1;self.messages.append(args)
        if self.error: raise self.error
        return "<smtp-123@example.edu>"
    def close(self): self.closed=True


def manager(client):
    settings=get_settings();settings.email_send_delay_seconds=0;settings.min_email_send_delay_seconds=0;settings.max_emails_per_day=200
    return DeliveryManager(settings,lambda:client)


def test_success_transition_records_smtp_message_id():
    batch_id,pid=seed();smtp=FakeClient();delivery=manager(smtp);delivery._send_one(batch_id,pid)
    with SessionLocal() as db:
        p=db.get(Participant,pid);assert p.status==DeliveryStatus.SENT;assert p.smtp_message_id=="<smtp-123@example.edu>";assert len(p.attempts)==1
        assert p.attempts[0].certificate_path==p.certificate_path
    assert smtp.messages[0][2]=='Hi Ada'
    assert smtp.messages[0][3]=='For {workshop_name}; welcome Ada'
    allowance=delivery.allowance();assert allowance["successful"]==1;assert allowance["used"]==1


def test_definite_and_uncertain_failures_are_distinct():
    b1,p1=seed();manager(FakeClient(DefiniteSendError("bad address")))._send_one(b1,p1)
    b2,p2=seed();manager(FakeClient(UncertainSendError("timeout after submit")))._send_one(b2,p2)
    with SessionLocal() as db:
        assert db.get(Participant,p1).status==DeliveryStatus.FAILED
        assert db.get(Participant,p2).status==DeliveryStatus.UNCERTAIN


def test_uncertain_submission_is_never_automatically_retried():
    batch_id,pid=seed();client=FakeClient(UncertainSendError("unknown acceptance"));manager(client)._send_one(batch_id,pid)
    assert client.calls==1
    with SessionLocal() as db:
        assert db.get(Participant,pid).status==DeliveryStatus.UNCERTAIN
        record=db.scalars(__import__('sqlalchemy').select(SendRecord).where(SendRecord.participant_id==pid)).one()
        assert record.status=="UNCERTAIN" and record.counts_against_limit


def test_transient_failure_is_retried_then_recorded_failed(monkeypatch):
    monkeypatch.setattr("app.services.delivery.time.sleep",lambda _:None)
    batch_id,pid=seed();client=FakeClient(TransientSendError("temporary restriction"));manager(client)._send_one(batch_id,pid)
    assert client.calls==3
    with SessionLocal() as db:
        assert db.get(Participant,pid).status==DeliveryStatus.FAILED


def test_restart_recovery_never_blindly_resends():
    batch_id,pid=seed(DeliveryStatus.SENDING);delivery=manager(FakeClient());record_id=delivery.reserve_send(batch_id,pid,"BULK");assert delivery.recover()==1
    with SessionLocal() as db:
        assert db.get(Participant,pid).status==DeliveryStatus.UNCERTAIN
        assert db.get(SendRecord,record_id).status=="UNCERTAIN"


def test_rolling_limit_is_persistent_and_definite_failures_release_slots():
    delivery=manager(FakeClient());delivery.settings.max_emails_per_day=2
    first=delivery.reserve_send(None,None,"TEST");second=delivery.reserve_send(None,None,"TEST")
    assert first and second and delivery.reserve_send(None,None,"TEST") is None
    delivery.finish_reservation(first,"SENT",message_id="one")
    delivery.finish_reservation(second,"FAILED",error="definite rejection")
    stats=delivery.allowance();assert stats["limit"]==2;assert stats["used"]==1;assert stats["remaining"]==1;assert stats["successful"]==1;assert stats["failed"]==1
    assert delivery.reserve_send(None,None,"TEST")


def test_application_cap_can_be_disabled_while_activity_is_still_counted():
    delivery=manager(FakeClient());delivery.settings.max_emails_per_day=None
    record_id=delivery.reserve_send(None,None,"TEST")
    assert record_id
    delivery.finish_reservation(record_id,"SENT",message_id="one")
    stats=delivery.allowance()
    assert stats['enabled'] is False and stats['limit'] is None and stats['remaining'] is None
    assert stats['used']==1 and 'SMTP provider' in stats['notice']


def test_records_older_than_24_hours_leave_the_rolling_window():
    from datetime import datetime, timedelta, timezone
    delivery=manager(FakeClient());delivery.settings.max_emails_per_day=1
    record_id=delivery.reserve_send(None,None,"TEST")
    with SessionLocal() as db:
        record=db.get(SendRecord,record_id);record.reserved_at=datetime.now(timezone.utc)-timedelta(hours=25);db.commit()
    assert delivery.allowance()["remaining"]==1


def test_complete_smtp_submission_slots_never_overlap():
    delivery=manager(FakeClient());active=0;maximum=0;lock=threading.Lock()
    def submit():
        nonlocal active,maximum
        with delivery.submission_slot():
            with lock:
                active+=1;maximum=max(maximum,active)
            time.sleep(.02)
            with lock: active-=1
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _:submit(),range(3)))
    assert maximum==1


def test_pause_recheck_returns_claimed_participant_to_pending_without_sending():
    batch_id,pid=seed();client=FakeClient();delivery=manager(client)
    @contextmanager
    def pause_before_submission():
        with SessionLocal() as db:
            db.get(Batch,batch_id).is_paused=True;db.commit()
        yield
    delivery.submission_slot=pause_before_submission
    delivery._send_one(batch_id,pid)
    assert client.calls==0
    with SessionLocal() as db:
        assert db.get(Participant,pid).status==DeliveryStatus.PENDING
        record=db.scalars(__import__('sqlalchemy').select(SendRecord).where(SendRecord.participant_id==pid)).one()
        assert record.status=="CANCELLED" and not record.counts_against_limit


def test_rate_limit_pauses_batch_and_records_definite_failure():
    batch_id,pid=seed();client=FakeClient(TransientSendError("Gmail rate limit",smtp_code=421,rate_limited=True));delivery=manager(client)
    delivery._send_one(batch_id,pid)
    assert client.calls==1
    with SessionLocal() as db:
        assert db.get(Batch,batch_id).is_paused is True
        assert db.get(Participant,pid).status==DeliveryStatus.FAILED


def test_atomic_claim_prevents_concurrent_duplicate_submission():
    batch_id,pid=seed();client=FakeClient();delivery=manager(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _:delivery._send_one(batch_id,pid),range(2)))
    assert client.calls==1
    with SessionLocal() as db:
        assert db.get(Participant,pid).status==DeliveryStatus.SENT


def test_adaptive_interval_speeds_up_after_healthy_sends_and_backs_off():
    client=FakeClient();delivery=manager(client)
    delivery.settings.min_email_send_delay_seconds=3
    delivery.settings.healthy_sends_before_speedup=2
    delivery._current_interval=5
    delivery.record_healthy_send();delivery.record_healthy_send()
    assert delivery._current_interval==4.5
    delivery.record_temporary_failure(retry_after=12)
    assert delivery._current_interval==12


def test_pacing_targets_submission_start_times_not_completion_times(monkeypatch):
    delivery=manager(FakeClient());delivery._current_interval=5;delivery._last_send=100
    clock={"now":104.0};sleeps=[]
    monkeypatch.setattr("app.services.delivery.time.monotonic",lambda:clock["now"])
    def advance(seconds):
        sleeps.append(seconds);clock["now"]+=seconds
    monkeypatch.setattr("app.services.delivery.time.sleep",advance)
    with delivery.submission_slot():
        clock["now"]+=4
    with delivery.submission_slot():
        pass
    assert sleeps==[1.0,1.0]


def test_single_worker_processes_200_recipients_with_one_client_session():
    started=time.perf_counter()
    with SessionLocal() as db:
        batch=Batch(sender_email="sender@example.edu",send_confirmed=True,email_subject="Hi {name}",email_body="Your workshop certificate is attached.",send_job_total=200)
        db.add(batch);db.flush()
        path=Path("data/test-data/benchmark.pdf");path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b"%PDF-test")
        render_version_path(path.resolve()).write_text(RENDER_STYLE_VERSION,encoding="utf-8")
        for index in range(200):
            db.add(Participant(batch_id=batch.id,row_number=index+2,name=f"Participant {index}",email=f"user{index}@example.edu",normalized_email=f"user{index}@example.edu",is_valid=True,certificate_path=str(path.resolve()),certificate_revision=batch.certificate_revision,idempotency_key=f"cert-{batch.id}-{index}"))
        db.commit();batch_id=batch.id
    client=FakeClient();factory_calls=0
    def factory():
        nonlocal factory_calls
        factory_calls+=1
        return client
    settings=get_settings();settings.email_send_delay_seconds=0;settings.min_email_send_delay_seconds=0;settings.max_emails_per_day=200
    delivery=DeliveryManager(settings,factory)
    delivery._run(batch_id)
    elapsed=time.perf_counter()-started
    with SessionLocal() as db:
        sent=db.scalar(__import__('sqlalchemy').select(__import__('sqlalchemy').func.count()).select_from(Participant).where(Participant.status==DeliveryStatus.SENT))
    assert sent==200 and client.calls==200
    assert factory_calls==1 and client.closed
    assert elapsed<15

