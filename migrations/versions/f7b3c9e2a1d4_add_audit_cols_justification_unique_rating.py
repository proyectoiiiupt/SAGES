"""Add user_id and created_at to request_justifications and unique request_id on ratings

Revision ID: f7b3c9e2a1d4
Revises: e4a9b2c1d8f0
Create Date: 2026-11-20 15:43:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7b3c9e2a1d4'
down_revision = 'e4a9b2c1d8f0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'request_justifications',
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        schema='sages'
    )
    op.create_foreign_key(
        'fk_request_justifications_user_id',
        'request_justifications',
        'users',
        ['user_id'],
        ['id'],
        source_schema='sages',
        referent_schema='sages'
    )
    op.add_column(
        'request_justifications',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='sages'
    )
    op.create_unique_constraint(
        'uq_ratings_request_id',
        'ratings',
        ['request_id'],
        schema='sages'
    )


def downgrade():
    op.drop_constraint('uq_ratings_request_id', 'ratings', schema='sages', type_='unique')
    op.drop_column('request_justifications', 'created_at', schema='sages')
    op.drop_constraint('fk_request_justifications_user_id', 'request_justifications', schema='sages', type_='foreignkey')
    op.drop_column('request_justifications', 'user_id', schema='sages')
