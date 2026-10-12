from django.db import migrations

# Composite foreign keys guarantee that a branch-access row can only link a membership and a
# branch belonging to the same organization as the row itself.
FORWARD = """
ALTER TABLE branches_membershipbranchaccess
    ADD CONSTRAINT branches_access_membership_same_org
    FOREIGN KEY (organization_id, membership_id)
    REFERENCES tenancy_organizationmembership (organization_id, id)
    ON DELETE CASCADE;
ALTER TABLE branches_membershipbranchaccess
    ADD CONSTRAINT branches_access_branch_same_org
    FOREIGN KEY (organization_id, branch_id)
    REFERENCES branches_branch (organization_id, id)
    ON DELETE CASCADE;
"""

REVERSE = """
ALTER TABLE branches_membershipbranchaccess DROP CONSTRAINT branches_access_membership_same_org;
ALTER TABLE branches_membershipbranchaccess DROP CONSTRAINT branches_access_branch_same_org;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("branches", "0001_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
