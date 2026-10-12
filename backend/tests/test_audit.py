import pytest
from django.db import connection
from django.db.utils import InternalError, ProgrammingError

from apps.audit_logs.models import AuditEvent
from apps.audit_logs.services import record_event
from tests.factories import api_client


@pytest.mark.django_db
class TestAuditLog:
    def test_record_event_redacts_secrets(self, owner):
        event = record_event(
            action="test.secret",
            actor=owner["user"],
            organization=owner["organization"],
            metadata={"token": "super-secret", "nested": {"password": "x"}, "ok": "visible"},
        )
        assert event.metadata["token"] == "[redacted]"
        assert event.metadata["nested"]["password"] == "[redacted]"
        assert event.metadata["ok"] == "visible"

    def test_orm_rejects_updates_and_deletes(self, owner):
        event = record_event(
            action="test.append", actor=owner["user"], organization=owner["organization"]
        )
        with pytest.raises(RuntimeError):
            event.save()
        with pytest.raises(RuntimeError):
            event.delete()

    def test_database_trigger_rejects_update(self, owner):
        event = record_event(
            action="test.trigger", actor=owner["user"], organization=owner["organization"]
        )
        with pytest.raises((InternalError, ProgrammingError)):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE audit_logs_auditevent SET action = %s WHERE id = %s",
                    ["tampered", str(event.pk)],
                )

    def test_creating_a_branch_writes_an_audit_row(self, owner):
        client = api_client(owner["user"], organization=owner["organization"])
        client.post("/api/v1/branches/", {"code": "AUD", "name": "Audit"}, format="json")
        assert AuditEvent.objects.filter(
            organization=owner["organization"], action="branches.created"
        ).exists()
