from fastapi.testclient import TestClient
from PIL import Image
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import uuid

from app.database import SessionLocal
from app.main import app
from app.models import Batch, DEFAULT_EMAIL_BODY, DEFAULT_EMAIL_SUBJECT, DeliveryAttempt, DeliveryStatus, Participant, SendRecord
from app.services.rendering import RENDER_STYLE_VERSION, render_version_path


client=TestClient(app)


def test_session_creation_normalizes_name_and_generates_uuid():
    response=client.post('/api/batches',json={'name':'  DevOps   Workshop  ','workshop_name':'Workshop'})
    assert response.status_code==200
    created=response.json()
    assert created['name']=='DevOps Workshop'
    assert str(uuid.UUID(created['id']))==created['id']
    with SessionLocal() as db:
        stored=db.get(Batch,created['id'])
        assert stored.name_normalized=='devops workshop'


def test_session_name_rejects_empty_whitespace_and_over_100_characters():
    for name in ['', '   \t  ', 'x'*101]:
        assert client.post('/api/batches',json={'name':name}).status_code==422
    accepted=client.post('/api/batches',json={'name':'x'*100})
    assert accepted.status_code==200 and len(accepted.json()['name'])==100


def test_session_name_is_unique_ignoring_case_and_whitespace():
    first=client.post('/api/batches',json={'name':'DevOps Workshop'})
    duplicate=client.post('/api/batches',json={'name':'  devops   workshop  '})
    assert first.status_code==200
    assert duplicate.status_code==409
    assert duplicate.json()['detail']=='A session named "devops workshop" already exists'


def test_concurrent_duplicate_session_creation_allows_exactly_one():
    def create(name: str):
        with TestClient(app) as concurrent_client:
            return concurrent_client.post('/api/batches',json={'name':name})

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses=list(executor.map(create,['Concurrent Workshop',' concurrent   workshop ']))
    assert sorted(response.status_code for response in responses)==[200,409]


def test_existing_session_can_be_listed_and_selected_by_generated_id():
    created=client.post('/api/batches',json={'name':'Selectable Session'}).json()
    listed=client.get('/api/batches')
    selected=client.get(f"/api/batches/{created['id']}")
    assert listed.status_code==200
    assert any(row['id']==created['id'] and row['name']=='Selectable Session' for row in listed.json())
    assert selected.status_code==200 and selected.json()['name']=='Selectable Session'


def test_participant_edits_persist_revalidate_and_invalidate_unsent_certificate(tmp_path):
    batch=client.post('/api/batches',json={'name':'Edits','workshop_name':'DevOps'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\nDuplicate,ADA@example.edu\n','text/csv')}).json()
    first,duplicate=imported['participants']
    pdf=tmp_path/'ada.pdf';pdf.write_bytes(b'%PDF');render_version_path(pdf).write_text(RENDER_STYLE_VERSION,encoding='utf-8')
    with SessionLocal() as db:
        row=db.get(Participant,first['id']);row.certificate_path=str(pdf);row.filename='ada.pdf';db.commit()
    changed=client.patch(f"/api/participants/{first['id']}",json={'name':'Ada Lovelace','email':'ada.new@example.edu'})
    assert changed.status_code==200
    rows={row['id']:row for row in changed.json()['participants']}
    assert rows[first['id']]['name']=='Ada Lovelace'
    assert rows[first['id']]['certificate_current'] is False and rows[first['id']]['filename'] is None
    assert rows[duplicate['id']]['is_valid'] is True
    assert changed.json()['import_counts']['invalid']==0


def test_invalid_participant_edit_is_persisted_with_specific_feedback():
    batch=client.post('/api/batches',json={'name':'Validation','workshop_name':'DevOps'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\n','text/csv')}).json()
    response=client.patch(f"/api/participants/{imported['participants'][0]['id']}",json={'email':'not-an-email'})
    assert response.status_code==200
    participant=response.json()['participants'][0]
    assert participant['email']=='not-an-email' and participant['is_valid'] is False
    assert participant['validation_error']


def test_sent_participant_identity_is_immutable():
    batch=client.post('/api/batches',json={'name':'Immutable','workshop_name':'DevOps'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\n','text/csv')}).json()
    participant_id=imported['participants'][0]['id']
    with SessionLocal() as db:
        row=db.get(Participant,participant_id);row.status=DeliveryStatus.SENT;db.commit()
    response=client.patch(f"/api/participants/{participant_id}",json={'email':'changed@example.edu'})
    assert response.status_code==409
    with SessionLocal() as db:
        assert db.get(Participant,participant_id).email=='ada@example.edu'


def test_failed_replacement_import_keeps_active_dataset():
    batch=client.post('/api/batches',json={'name':'Atomic','workshop_name':'DevOps'}).json()
    first=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\n','text/csv')}).json()
    failed=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('bad.csv',b'Wrong,Columns\nx,y\n','text/csv')})
    assert failed.status_code==422
    current=client.get(f"/api/batches/{batch['id']}").json()
    assert [row['id'] for row in current['participants']]==[first['participants'][0]['id']]


def test_generation_reports_durable_progress_and_completion(tmp_path, font_path):
    import time
    batch=client.post('/api/batches',json={'name':'Progress','workshop_name':'DevOps'}).json()
    client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\nGrace,grace@example.edu\n','text/csv')})
    template=tmp_path/'template.png';Image.new('RGB',(500,300),'white').save(template)
    with SessionLocal() as db:
        stored=db.get(Batch,batch['id']);stored.template_path=str(template);stored.font_path=str(font_path);db.commit()
    started=client.post(f"/api/batches/{batch['id']}/generate")
    assert started.status_code==200 and started.json()=={'started':True,'total':2}
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        current=client.get(f"/api/batches/{batch['id']}").json()
        if current['generation']['status']!='RUNNING' and current['generation']['total']:
            break
        time.sleep(.02)
    progress=current['generation']
    assert progress['status']=='COMPLETED'
    assert progress['total']==progress['succeeded']==2
    assert progress['failed']==progress['remaining']==0 and progress['percent']==100


def test_new_batches_receive_email_defaults_without_overwriting_saved_content():
    first=client.post('/api/batches',json={'name':'First','workshop_name':'DevOps'}).json()
    assert first['email_subject']==DEFAULT_EMAIL_SUBJECT=='Your Certificate of Participation'
    assert first['email_body']==DEFAULT_EMAIL_BODY=='''Hi {name},

Thank you for participating in our event!

We appreciate your time, enthusiasm, and involvement. Please find your personalized certificate of participation attached to this email.

We hope you enjoyed the experience and look forward to seeing you at our future events.

Best regards,
Event Organizing Team'''
    assert not any(value in first['email_body'] for value in ('DevOps','SLIIT','Sysco','Workshop'))
    with SessionLocal() as db:
        stored=db.get(Batch,first['id']);stored.email_subject='My saved subject';stored.email_body='My saved body';db.commit()
    second=client.post('/api/batches',json={'name':'Second','workshop_name':'DevOps'}).json()
    refreshed=client.get(f"/api/batches/{first['id']}").json()
    assert refreshed['email_subject']=='My saved subject' and refreshed['email_body']=='My saved body'
    assert second['email_subject']==DEFAULT_EMAIL_SUBJECT and second['email_body']==DEFAULT_EMAIL_BODY


def test_email_configuration_no_longer_accepts_or_changes_legacy_workshop_name(monkeypatch):
    monkeypatch.setattr('app.main.allowed_senders',lambda:{'sender@example.edu'})
    created=client.post('/api/batches',json={'name':'Email configuration'}).json()
    with SessionLocal() as db:
        stored=db.get(Batch,created['id']);stored.workshop_name='Preserved legacy value';db.commit()
    response=client.put(f"/api/batches/{created['id']}/email",json={
        'sender_email':'sender@example.edu',
        'subject':'Certificate for {name}',
        'body':'The DevOps Workshop certificate for {name} is attached.',
        'workshop_name':'Must be ignored',
    })
    assert response.status_code==200
    configured=response.json()
    assert configured['email_subject']=='Certificate for {name}'
    assert configured['email_body']=='The DevOps Workshop certificate for {name} is attached.'
    assert 'workshop_name' not in configured
    with SessionLocal() as db:
        assert db.get(Batch,created['id']).workshop_name=='Preserved legacy value'


def test_sessions_are_independent_and_fresh_session_progress_starts_at_zero():
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        previous=Batch(name='Previous 167',workshop_name='DevOps',send_confirmed=True,send_job_total=167,send_job_started_at=now-timedelta(minutes=20),send_job_finished_at=now)
        db.add(previous);db.flush()
        for index in range(167):
            participant=Participant(batch_id=previous.id,row_number=index+2,name=f'Old {index}',email=f'person{index}@example.edu',normalized_email=f'person{index}@example.edu',canonical_email=f'person{index}@example.edu',is_valid=True,is_current_import=True,import_id='old-import',status=DeliveryStatus.SENT,idempotency_key=f'old-{previous.id}-{index}',sent_at=now)
            db.add(participant);db.flush()
            db.add(DeliveryAttempt(participant_id=participant.id,attempt_number=1,outcome='SENT',finished_at=now))
            db.add(SendRecord(batch_id=previous.id,participant_id=participant.id,kind='BULK',status='SENT',counts_against_limit=True,reserved_at=now,finished_at=now))
        previous.active_import_id='old-import';db.commit();previous_id=previous.id
    fresh=client.post('/api/batches',json={'name':'Fresh four','workshop_name':'Workshop'}).json()
    csv_data=b'Name,Email\nOne,person0@example.edu\nTwo,two@example.edu\nThree,three@example.edu\nFour,four@example.edu\n'
    imported=client.post(f"/api/batches/{fresh['id']}/participants/import",files={'file':('four.csv',csv_data,'text/csv')}).json()
    assert imported['counts']=={'TOTAL':4,'PENDING':4,'SENDING':0,'SENT':0,'FAILED':0,'UNCERTAIN':0}
    assert imported['progress']['total']==0 and imported['progress']['percent']==0 and imported['progress']['elapsed_seconds']==0
    assert imported['template_path'] is False and imported['font_path'] is False and imported['sender_email'] is None
    previous=client.get(f'/api/batches/{previous_id}').json()
    assert previous['counts']['SENT']==167 and previous['progress']['sent']==167 and len(previous['participants'])==167
    assert previous['allowance']['used']==167 and imported['allowance']['used']==167
    listed=client.get('/api/batches').json()
    assert {previous_id,fresh['id']} <= {session['id'] for session in listed}
    assert all(session['created_at'] for session in listed)


def test_replacing_session_dataset_requires_confirmation_and_resets_only_live_progress():
    batch=client.post('/api/batches',json={'name':'Replacement','workshop_name':'DevOps'}).json()
    first=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('first.csv',b'Name,Email\nAda,ada@example.edu\n','text/csv')}).json()
    original_id=first['participants'][0]['id']
    with SessionLocal() as db:
        stored=db.get(Batch,batch['id']);stored.send_job_total=1;stored.send_job_started_at=datetime.now(timezone.utc)-timedelta(minutes=1);stored.send_job_finished_at=datetime.now(timezone.utc)
        participant=db.get(Participant,original_id);participant.status=DeliveryStatus.SENT
        db.add(DeliveryAttempt(participant_id=participant.id,attempt_number=1,outcome='SENT'));db.commit()
    replacement={'file':('second.csv',b'Name,Email\nGrace,grace@example.edu\n','text/csv')}
    blocked=client.post(f"/api/batches/{batch['id']}/participants/import",files=replacement)
    assert blocked.status_code==409 and blocked.json()['detail']['code']=='replace_confirmation_required'
    assert client.get(f"/api/batches/{batch['id']}").json()['participants'][0]['id']==original_id
    replaced=client.post(f"/api/batches/{batch['id']}/participants/import",files=replacement,data={'confirm_replace':'true'}).json()
    assert [row['email'] for row in replaced['participants']]==['grace@example.edu']
    assert replaced['counts']['PENDING']==1 and replaced['progress']['total']==0 and replaced['progress']['elapsed_seconds']==0
    with SessionLocal() as db:
        historical=db.get(Participant,original_id)
        assert historical.status==DeliveryStatus.SENT and historical.is_current_import is False and len(historical.attempts)==1


def test_batch_import_and_report_are_functional():
    batch=client.post('/api/batches',json={'name':'DevOps','workshop_name':'CI Workshop'}).json()
    response=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\nBad,nope\n','text/csv')})
    assert response.status_code==200
    body=response.json();assert len(body['participants'])==2;assert body['counts']['TOTAL']==1
    report=client.get(f"/api/batches/{batch['id']}/report")
    assert report.status_code==200;assert b'SMTP Message ID' in report.content


def test_google_forms_csv_import_maps_name_and_certificate_email_automatically():
    batch=client.post('/api/batches',json={'name':'Forms','workshop_name':'DevOps'}).json()
    csv_data=('Timestamp,Name,Email Address (To send the E-Certificate),Unrelated\n'
              '10/22/2026 10:00,Ada Lovelace,ada@example.edu,ignore\n').encode()
    response=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('forms.csv',csv_data,'text/csv')})
    assert response.status_code==200
    participant=response.json()['participants'][0]
    assert participant['name']=='Ada Lovelace' and participant['email']=='ada@example.edu'


def test_exact_google_forms_headers_import_173_rows_and_keep_duplicate_visible():
    batch=client.post('/api/batches',json={'name':'Large Forms','workshop_name':'DevOps'}).json()
    lines=['Name,Email Address (To send the E-Certificate)']
    lines.extend(f'Participant {index},person{index}@example.edu' for index in range(1,173))
    lines.append('Duplicate Person,PERSON1@example.edu')
    response=client.post(
        f"/api/batches/{batch['id']}/participants/import",
        files={'file':('forms.csv',('\n'.join(lines)+'\n').encode(),'text/csv')},
    )
    assert response.status_code==200
    body=response.json()
    assert len(body['participants'])==173
    assert body['import_counts']=={'total':173,'valid':172,'invalid':1,'duplicates':1,'preserved':0}
    duplicate=body['participants'][-1]
    assert duplicate['email']=='PERSON1@example.edu'
    assert duplicate['is_valid'] is False
    assert duplicate['validation_error']=='Duplicate email in this import'


def test_reimport_preserves_historical_delivery_snapshots_and_archives_removed_rows():
    batch=client.post('/api/batches',json={'name':'Reimport','workshop_name':'DevOps'}).json()
    original=b'Name,Email\nSent,sent@example.edu\nFailed,failed@example.edu\nPending,pending@example.edu\nUncertain,uncertain@example.edu\nRemoved,removed@example.edu\n'
    first=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('first.csv',original,'text/csv')}).json()
    statuses=[DeliveryStatus.SENT,DeliveryStatus.FAILED,DeliveryStatus.PENDING,DeliveryStatus.UNCERTAIN]
    original_ids={item['email']:item['id'] for item in first['participants']}
    with SessionLocal() as db:
        for item,status in zip(first['participants'][:4],statuses):
            participant=db.get(Participant,item['id']);participant.status=status
            db.add(DeliveryAttempt(participant_id=participant.id,attempt_number=1,outcome=status.value))
        db.commit()
    replacement=(
        'Name,Email Address (To send the E-Certificate)\n'
        'Sent Updated,sent@example.edu\nFailed,failed@example.edu\nPending,pending@example.edu\nUncertain,uncertain@example.edu\nNew,new@example.edu\n'
    ).encode()
    response=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('second.csv',replacement,'text/csv')},data={'confirm_replace':'true'})
    assert response.status_code==200
    body=response.json()
    assert len(body['participants'])==5
    assert body['import_counts']['preserved']==1
    by_email={item['email']:item for item in body['participants']}
    assert by_email['sent@example.edu']['status']=='PENDING'
    assert by_email['sent@example.edu']['id']!=original_ids['sent@example.edu']
    assert by_email['sent@example.edu']['is_excluded'] is True
    assert by_email['sent@example.edu']['previous_delivery']['participant_id']==original_ids['sent@example.edu']
    with SessionLocal() as db:
        removed=db.get(Participant,original_ids['removed@example.edu'])
        assert removed is not None and removed.is_current_import is False
        historical=db.get(Participant,original_ids['sent@example.edu'])
        assert historical.name=='Sent' and historical.status==DeliveryStatus.SENT
        assert len(historical.attempts)==1


def test_unrecognized_headers_return_friendly_manual_mapping_metadata():
    batch=client.post('/api/batches',json={'name':'Custom','workshop_name':'DevOps'}).json()
    csv_data=b'Badge Text,Contact Point,Timestamp\nAda,ada@example.edu,now\n'
    response=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('custom.csv',csv_data,'text/csv')})
    assert response.status_code==422
    detail=response.json()['detail']
    assert detail['code']=='column_mapping_required'
    assert detail['headers']==['Badge Text','Contact Point','Timestamp']
    mapped=client.post(
        f"/api/batches/{batch['id']}/participants/import",
        files={'file':('custom.csv',csv_data,'text/csv')},
        data={'name_column':' badge text ','email_column':'CONTACT POINT'},
    )
    assert mapped.status_code==200
    assert mapped.json()['participants'][0]['email']=='ada@example.edu'


def test_live_preview_uses_participant_and_unsaved_region(tmp_path, font_path):
    batch=client.post('/api/batches',json={'name':'Preview','workshop_name':'DevOps'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda Lovelace,ada@example.edu\n','text/csv')}).json()
    template=tmp_path/'template.png';Image.new('RGB',(800,500),'white').save(template)
    with SessionLocal() as db:
        stored=db.get(Batch,batch['id']);stored.template_path=str(template);stored.font_path=str(font_path);db.commit()
    payload={'participant_id':imported['participants'][0]['id'],'x':.2,'y':.35,'w':.6,'h':.2,'font_size':100,'min_font_size':18,'auto_fit':True,'vertical_offset':4}
    response=client.post(f"/api/batches/{batch['id']}/render-preview",json=payload)
    assert response.status_code==200
    assert response.headers['content-type']=='image/png'
    assert int(response.headers['x-actual-font-size'])<=100
    assert Image.open(__import__('io').BytesIO(response.content)).size==(800,500)


def test_send_requires_exact_confirmation():
    batch=client.post('/api/batches',json={'name':'DevOps','workshop_name':'CI'}).json()
    response=client.post(f"/api/batches/{batch['id']}/send",json={'confirmation':'yes'})
    assert response.status_code==400


def test_pre_style_change_certificate_is_outdated_and_not_ready(tmp_path):
    batch=client.post('/api/batches',json={'name':'Old style','workshop_name':'CI'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\n','text/csv')}).json()
    participant_id=imported['participants'][0]['id'];pdf=tmp_path/'old.pdf';pdf.write_bytes(b'%PDF-old')
    with SessionLocal() as db:
        row=db.get(Participant,participant_id);row.certificate_path=str(pdf);row.filename='old.pdf';db.commit()
    current=client.get(f"/api/batches/{batch['id']}").json()
    assert current['ready_count']==0 and current['outdated_certificate_count']==1
    assert current['participants'][0]['certificate_current'] is False
    assert client.get(f"/api/participants/{participant_id}/certificate").status_code==409


def test_removed_test_send_endpoint_is_not_available():
    batch=client.post('/api/batches',json={'name':'DevOps','workshop_name':'CI'}).json()
    assert client.post(f"/api/batches/{batch['id']}/send-test",json={}).status_code==404


def test_bulk_send_requires_current_pdf_for_every_pending_eligible_participant(tmp_path):
    batch=client.post('/api/batches',json={'name':'Complete PDFs','workshop_name':'CI'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\nGrace,grace@example.edu\n','text/csv')}).json()
    pdf=tmp_path/'current.pdf';pdf.write_bytes(b'%PDF-current');render_version_path(pdf).write_text(RENDER_STYLE_VERSION,encoding='utf-8')
    with SessionLocal() as db:
        db.get(Participant,imported['participants'][0]['id']).certificate_path=str(pdf);db.commit()
    response=client.post(f"/api/batches/{batch['id']}/send",json={'confirmation':'SEND 1'})
    assert response.status_code==409
    assert 'all 2 pending eligible participants' in response.json()['detail']


def test_retry_failed_never_changes_uncertain_or_sent():
    batch=client.post('/api/batches',json={'name':'Retry','workshop_name':'CI'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\nGrace,grace@example.edu\nLinus,linus@example.edu\n','text/csv')}).json()
    with SessionLocal() as db:
        statuses=[DeliveryStatus.FAILED,DeliveryStatus.UNCERTAIN,DeliveryStatus.SENT]
        for participant,status in zip(imported['participants'],statuses): db.get(Participant,participant['id']).status=status
        db.commit()
    response=client.post(f"/api/batches/{batch['id']}/retry-failed")
    assert response.status_code==200 and response.json()['reset']==1
    current=client.get(f"/api/batches/{batch['id']}").json()['participants']
    assert [row['status'] for row in current]==['PENDING','UNCERTAIN','SENT']


def test_uncertain_reconciliation_is_explicit_audited_and_never_directly_retried():
    batch=client.post('/api/batches',json={'name':'Reconcile','workshop_name':'CI'}).json()
    imported=client.post(f"/api/batches/{batch['id']}/participants/import",files={'file':('people.csv',b'Name,Email\nAda,ada@example.edu\nGrace,grace@example.edu\n','text/csv')}).json()
    with SessionLocal() as db:
        for item in imported['participants']:
            participant=db.get(Participant,item['id']);participant.status=DeliveryStatus.UNCERTAIN
            db.add(DeliveryAttempt(participant_id=participant.id,attempt_number=1,outcome='UNCERTAIN',error_code='UNCERTAIN_SUBMISSION',error_reason='Acceptance unknown'))
            db.add(SendRecord(batch_id=batch['id'],participant_id=participant.id,kind='BULK',status='UNCERTAIN',counts_against_limit=True))
        db.commit()
    wrong=client.post(f"/api/participants/{imported['participants'][0]['id']}/reconcile",json={'action':'CONFIRM_SENT','confirmation':'yes','note':''})
    assert wrong.status_code==400
    sent=client.post(f"/api/participants/{imported['participants'][0]['id']}/reconcile",json={'action':'CONFIRM_SENT','confirmation':'CONFIRM SENT','note':'Checked Gmail Sent'})
    failed=client.post(f"/api/participants/{imported['participants'][1]['id']}/reconcile",json={'action':'CONFIRM_NOT_SENT','confirmation':'CONFIRM NOT SENT','note':'Not present in Sent'})
    assert sent.status_code==200 and failed.status_code==200
    with SessionLocal() as db:
        first=db.get(Participant,imported['participants'][0]['id']);second=db.get(Participant,imported['participants'][1]['id'])
        assert first.status==DeliveryStatus.SENT and second.status==DeliveryStatus.FAILED
        assert first.attempts[0].outcome=='UNCERTAIN' and first.attempts[0].reconciliation_action=='CONFIRM_SENT'
        assert second.attempts[0].reconciliation_action=='CONFIRM_NOT_SENT'
        records=db.scalars(__import__('sqlalchemy').select(SendRecord).where(SendRecord.batch_id==batch['id'])).all()
        assert {record.status for record in records}=={'SENT','FAILED'}
        assert all(record.counts_against_limit for record in records)

