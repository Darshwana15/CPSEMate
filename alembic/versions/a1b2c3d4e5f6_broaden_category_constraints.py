"""broaden category check constraints for multi-category support

Revision ID: a1b2c3d4e5f6
Revises: 392614d6779d
Create Date: 2026-09-02 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '392614d6779d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_CATEGORIES = "('VALVE', 'PUMP', 'GASKET', 'FLANGE', 'BEARING', 'FASTENER')"


def upgrade() -> None:
    """Broaden category constraints on national_material and material tables."""

    # 1. national_material: DROP legacy valve-only constraint, ADD multi-category
    op.drop_constraint(
        'chk_national_material_category_valve',
        'national_material',
        type_='check'
    )
    op.create_check_constraint(
        'chk_national_material_category_valid',
        'national_material',
        f"category IN {VALID_CATEGORIES}"
    )

    # 2. material: DROP legacy valve-only constraint, ADD multi-category
    op.drop_constraint(
        'chk_material_category_valve',
        'material',
        type_='check'
    )
    op.create_check_constraint(
        'chk_material_category_valid',
        'material',
        f"category IS NULL OR category IN {VALID_CATEGORIES}"
    )


def downgrade() -> None:
    """Restore original valve-only category constraints."""

    # 1. national_material: revert to valve-only
    op.drop_constraint(
        'chk_national_material_category_valid',
        'national_material',
        type_='check'
    )
    op.create_check_constraint(
        'chk_national_material_category_valve',
        'national_material',
        "category = 'VALVE'"
    )

    # 2. material: revert to valve-only
    op.drop_constraint(
        'chk_material_category_valid',
        'material',
        type_='check'
    )
    op.create_check_constraint(
        'chk_material_category_valve',
        'material',
        "category IS NULL OR category = 'VALVE'"
    )
