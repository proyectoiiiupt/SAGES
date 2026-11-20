"""Expand RequestEvidence file_name and file_path to VARCHAR(255)

Revision ID: e4a9b2c1d8f0
Revises: 3acc7b7bbf8a
Create Date: 2026-11-20 15:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4a9b2c1d8f0'
down_revision = '3acc7b7bbf8a'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'request_evidences',
        'file_name',
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
        schema='sages'
    )
    op.alter_column(
        'request_evidences',
        'file_path',
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
        schema='sages'
    )


def downgrade():
    op.alter_column(
        'request_evidences',
        'file_path',
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=False,
        schema='sages'
    )
    op.alter_column(
        'request_evidences',
        'file_name',
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=False,
        schema='sages'
    )
