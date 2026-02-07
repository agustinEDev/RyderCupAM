"""refactor tee_categories (7→5) and add gender fields

Revision ID: c3d5e7f9a1b2
Revises: b9e4f1a3c7d2
Create Date: 2026-02-07 20:00:00.000000

Refactors TeeCategory from 7 gender-combined values to 5 difficulty-only values.
Adds gender column to golf_course_tees and users tables.
No data migration needed (all users are test data).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d5e7f9a1b2"
down_revision: Union[str, None] = "b9e4f1a3c7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add gender column to users table
    op.add_column("users", sa.Column("gender", sa.String(10), nullable=True))

    # 2. Add tee_gender column to golf_course_tees table
    op.add_column("golf_course_tees", sa.Column("tee_gender", sa.String(10), nullable=True))

    # 3. Drop old unique constraint on (golf_course_id, tee_category)
    op.drop_constraint("uq_golf_course_tees_category", "golf_course_tees", type_="unique")

    # 4. Replace tee_category_enum with new 5 values
    # Drop old enum and create new one
    op.execute("ALTER TABLE golf_course_tees ALTER COLUMN tee_category TYPE VARCHAR(20)")
    op.execute("DROP TYPE IF EXISTS tee_category_enum")
    op.execute(
        "CREATE TYPE tee_category_enum AS ENUM "
        "('CHAMPIONSHIP', 'AMATEUR', 'SENIOR', 'FORWARD', 'JUNIOR')"
    )
    op.execute(
        "ALTER TABLE golf_course_tees ALTER COLUMN tee_category "
        "TYPE tee_category_enum USING tee_category::tee_category_enum"
    )

    # 5. Create functional unique index for (golf_course_id, tee_category, COALESCE(tee_gender, 'NONE'))
    op.execute(
        "CREATE UNIQUE INDEX uq_golf_course_tees_cat_gender "
        "ON golf_course_tees (golf_course_id, tee_category, COALESCE(tee_gender, 'NONE'))"
    )


def downgrade() -> None:
    # Remove functional unique index
    op.execute("DROP INDEX IF EXISTS uq_golf_course_tees_cat_gender")

    # Revert tee_category_enum to old 7 values
    op.execute("ALTER TABLE golf_course_tees ALTER COLUMN tee_category TYPE VARCHAR(20)")
    op.execute("DROP TYPE IF EXISTS tee_category_enum")
    op.execute(
        "CREATE TYPE tee_category_enum AS ENUM "
        "('CHAMPIONSHIP_MALE', 'AMATEUR_MALE', 'SENIOR_MALE', "
        "'CHAMPIONSHIP_FEMALE', 'AMATEUR_FEMALE', 'SENIOR_FEMALE', 'JUNIOR')"
    )
    op.execute(
        "ALTER TABLE golf_course_tees ALTER COLUMN tee_category "
        "TYPE tee_category_enum USING tee_category::tee_category_enum"
    )

    # Restore old unique constraint
    op.create_unique_constraint(
        "uq_golf_course_tees_category", "golf_course_tees", ["golf_course_id", "tee_category"]
    )

    # Remove tee_gender from golf_course_tees
    op.drop_column("golf_course_tees", "tee_gender")

    # Remove gender from users
    op.drop_column("users", "gender")
