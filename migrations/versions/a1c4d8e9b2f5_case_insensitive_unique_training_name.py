"""Case-insensitive partial unique index on active Training names

Revision ID: a1c4d8e9b2f5
Revises: f7b3c9e2a1d4
Create Date: 2026-11-25 22:55:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1c4d8e9b2f5'
down_revision = 'f7b3c9e2a1d4'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE sages.trainings DROP CONSTRAINT IF EXISTS uq_module_training_name"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_module_training_name_lower "
        "ON sages.trainings (training_module_id, lower(name)) "
        "WHERE deleted_at IS NULL"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS sages.uq_module_training_name_lower")
    op.create_unique_constraint(
        'uq_module_training_name',
        'trainings',
        ['training_module_id', 'name'],
        schema='sages',
    )
