from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION audit_logs_reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit events are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_auditevent_append_only
    BEFORE UPDATE OR DELETE ON audit_logs_auditevent
    FOR EACH ROW EXECUTE FUNCTION audit_logs_reject_mutation();
"""

REVERSE = """
DROP TRIGGER IF EXISTS audit_logs_auditevent_append_only ON audit_logs_auditevent;
DROP FUNCTION IF EXISTS audit_logs_reject_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("audit_logs", "0001_initial")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
