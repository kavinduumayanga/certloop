import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.config import Settings
from app.database import ensure_unique_session_names, relocated_path


def test_application_sending_cap_is_optional_and_configurable():
    assert Settings(_env_file=None).max_emails_per_day is None
    assert Settings(_env_file=None,max_emails_per_day=350).max_emails_per_day==350


def test_stale_absolute_runtime_path_is_relocated_by_basename(tmp_path):
    uploads=tmp_path/'uploads';uploads.mkdir();current=uploads/'template.jpg';current.write_bytes(b'image')
    stale='/old/project/data/uploads/template.jpg'
    assert relocated_path(stale,uploads)==str(current.resolve())
    assert relocated_path('/old/project/data/uploads/missing.jpg',uploads).endswith('/old/project/data/uploads/missing.jpg')


def test_legacy_session_name_migration_preserves_ids_and_assigns_unique_names(tmp_path):
    legacy_engine=create_engine(f"sqlite:///{tmp_path/'legacy.db'}")
    with legacy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE batches (id VARCHAR PRIMARY KEY, name VARCHAR, name_normalized VARCHAR, created_at DATETIME)"))
        connection.execute(text("INSERT INTO batches (id,name,created_at) VALUES ('one','  Workshop   certificates  ','2024-01-01'),('two','workshop certificates','2024-01-02'),('three','   ','2024-01-03')"))
        ensure_unique_session_names(connection)
        rows=connection.execute(text("SELECT id,name,name_normalized FROM batches ORDER BY created_at")).all()

    assert [row.id for row in rows]==['one','two','three']
    assert [row.name for row in rows]==['Workshop certificates','workshop certificates 2','Session 1']
    assert len({row.name_normalized for row in rows})==3
    assert any(index['unique'] and index['name']=='ux_batches_name_normalized' for index in inspect(legacy_engine).get_indexes('batches'))


def test_smtp_performance_settings_are_active_configuration():
    settings = Settings(
        _env_file=None,
        delivery_concurrency=1,
        smtp_workers=1,
        smtp_connection_reuse=False,
        smtp_max_messages_per_connection=7,
        smtp_timeout_seconds=11,
        smtp_data_timeout_seconds=222,
        email_send_delay_seconds=5,
    )
    assert settings.smtp_connection_reuse is False
    assert settings.smtp_max_messages_per_connection == 7
    assert settings.smtp_timeout_seconds == 11
    assert settings.smtp_data_timeout_seconds == 222
    assert settings.email_send_delay_seconds == 5


@pytest.mark.parametrize("field", ["delivery_concurrency", "smtp_workers"])
def test_parallel_smtp_configuration_is_rejected(field: str):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: 2})
