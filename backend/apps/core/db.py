from django.db import migrations


def tenant_consistency_fk(
    table: str, column: str, ref_table: str, name: str, tenant_column: str = "organization_id"
) -> migrations.RunSQL:
    """Composite foreign key guaranteeing that `table.column` references a row in the same tenant.

    The referenced table must declare a unique constraint on (id, organization).
    """
    return migrations.RunSQL(
        sql=(
            f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
            f'FOREIGN KEY ("{column}", "{tenant_column}") '
            f'REFERENCES "{ref_table}" ("id", "{tenant_column}") ON DELETE RESTRICT;'
        ),
        reverse_sql=f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}";',
    )
