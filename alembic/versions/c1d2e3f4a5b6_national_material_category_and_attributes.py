"""add normalized_attributes and remove restrictive category check constraints

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-04 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add normalized_attributes JSONB to national_material
    op.add_column(
        'national_material',
        sa.Column('normalized_attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # 2. Make valve-specific columns on national_material nullable for non-valve support
    op.alter_column('national_material', 'valve_type', existing_type=sa.String(100), nullable=True)
    op.alter_column('national_material', 'size', existing_type=sa.String(100), nullable=True)
    op.alter_column('national_material', 'body_material', existing_type=sa.String(100), nullable=True)
    op.alter_column('national_material', 'pressure_class', existing_type=sa.String(100), nullable=True)
    op.alter_column('national_material', 'connection_type', existing_type=sa.String(100), nullable=True)
    op.alter_column('national_material', 'trim', existing_type=sa.String(100), nullable=True)
    op.alter_column('national_material', 'normalized_uom', existing_type=sa.String(50), nullable=True)

    # 3. Drop restrictive enum category check constraints
    op.drop_constraint('chk_national_material_category_valid', 'national_material', type_='check')
    op.drop_constraint('chk_material_category_valid', 'material', type_='check')


def downgrade() -> None:
    # 1. Recreate category check constraints
    op.create_check_constraint(
        'chk_material_category_valid',
        'material',
        "category IS NULL OR category IN ('VALVE', 'PUMP', 'GASKET', 'FLANGE', 'BEARING', 'FASTENER')"
    )
    op.create_check_constraint(
        'chk_national_material_category_valid',
        'national_material',
        "category IN ('VALVE', 'PUMP', 'GASKET', 'FLANGE', 'BEARING', 'FASTENER')"
    )

    # 2. Make columns not null
    op.alter_column('national_material', 'normalized_uom', existing_type=sa.String(50), nullable=False)
    op.alter_column('national_material', 'trim', existing_type=sa.String(100), nullable=False)
    op.alter_column('national_material', 'connection_type', existing_type=sa.String(100), nullable=False)
    op.alter_column('national_material', 'pressure_class', existing_type=sa.String(100), nullable=False)
    op.alter_column('national_material', 'body_material', existing_type=sa.String(100), nullable=False)
    op.alter_column('national_material', 'size', existing_type=sa.String(100), nullable=False)
    op.alter_column('national_material', 'valve_type', existing_type=sa.String(100), nullable=False)

    # 3. Drop normalized_attributes
    op.drop_column('national_material', 'normalized_attributes')
