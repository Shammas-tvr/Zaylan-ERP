from django.db import migrations

# A role assignment may only connect a membership and a role from its own organization.
FORWARD = """
ALTER TABLE access_control_membershiproleassignment
    ADD CONSTRAINT access_control_assignment_membership_same_org
    FOREIGN KEY (organization_id, membership_id)
    REFERENCES tenancy_organizationmembership (organization_id, id)
    ON DELETE CASCADE;
ALTER TABLE access_control_membershiproleassignment
    ADD CONSTRAINT access_control_assignment_role_same_org
    FOREIGN KEY (organization_id, role_id)
    REFERENCES access_control_role (organization_id, id);
"""

REVERSE = """
ALTER TABLE access_control_membershiproleassignment
    DROP CONSTRAINT access_control_assignment_membership_same_org;
ALTER TABLE access_control_membershiproleassignment
    DROP CONSTRAINT access_control_assignment_role_same_org;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("access_control", "0002_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
