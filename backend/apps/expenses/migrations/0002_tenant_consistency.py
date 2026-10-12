from django.db import migrations

FORWARD = """
ALTER TABLE expenses_recurringexpense
    ADD CONSTRAINT expenses_recurring_branch_same_org
    FOREIGN KEY (organization_id, branch_id)
    REFERENCES branches_branch (organization_id, id)
    ON DELETE RESTRICT;
ALTER TABLE expenses_expense
    ADD CONSTRAINT expenses_expense_branch_same_org
    FOREIGN KEY (organization_id, branch_id)
    REFERENCES branches_branch (organization_id, id)
    ON DELETE RESTRICT;
"""

REVERSE = """
ALTER TABLE expenses_expense DROP CONSTRAINT IF EXISTS expenses_expense_branch_same_org;
ALTER TABLE expenses_recurringexpense DROP CONSTRAINT IF EXISTS expenses_recurring_branch_same_org;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("expenses", "0001_initial"),
        ("branches", "0002_tenant_consistency"),
    ]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
