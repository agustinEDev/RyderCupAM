"""refactor tee_categories (7→5) and add gender fields

Revision ID: c3d5e7f9a1b2
Revises: b9e4f1a3c7d2
Create Date: 2026-02-07 20:00:00.000000

Refactors TeeCategory from 7 gender-combined values to 5 difficulty-only values.
Adds gender column to golf_course_tees and users tables.
Includes data migration to split combined tee_category values (e.g. CHAMPIONSHIP_MALE)
into separate tee_category (CHAMPIONSHIP) and tee_gender (MALE) columns.
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

    # 4. Convert tee_category to VARCHAR first (remove old enum constraint)
    op.execute("ALTER TABLE golf_course_tees ALTER COLUMN tee_category TYPE VARCHAR(20)")
    op.execute("DROP TYPE IF EXISTS tee_category_enum")

    # 5. Split legacy combined tee_category values into tee_category + tee_gender
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'MALE', tee_category = 'CHAMPIONSHIP' "
        "WHERE tee_category = 'CHAMPIONSHIP_MALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'FEMALE', tee_category = 'CHAMPIONSHIP' "
        "WHERE tee_category = 'CHAMPIONSHIP_FEMALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'MALE', tee_category = 'AMATEUR' "
        "WHERE tee_category = 'AMATEUR_MALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'FEMALE', tee_category = 'AMATEUR' "
        "WHERE tee_category = 'AMATEUR_FEMALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'MALE', tee_category = 'SENIOR' "
        "WHERE tee_category = 'SENIOR_MALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'FEMALE', tee_category = 'SENIOR' "
        "WHERE tee_category = 'SENIOR_FEMALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = NULL "
        "WHERE tee_category = 'JUNIOR'"
    )

    # 6. Create new enum with 5 values and cast column
    op.execute(
        "CREATE TYPE tee_category_enum AS ENUM "
        "('CHAMPIONSHIP', 'AMATEUR', 'SENIOR', 'FORWARD', 'JUNIOR')"
    )
    op.execute(
        "ALTER TABLE golf_course_tees ALTER COLUMN tee_category "
        "TYPE tee_category_enum USING tee_category::tee_category_enum"
    )

    # 7. Create functional unique index for (golf_course_id, tee_category, COALESCE(tee_gender, 'NONE'))
    op.execute(
        "CREATE UNIQUE INDEX uq_golf_course_tees_cat_gender "
        "ON golf_course_tees (golf_course_id, tee_category, COALESCE(tee_gender, 'NONE'))"
    )


def downgrade() -> None:
    # Remove functional unique index
    op.execute("DROP INDEX IF EXISTS uq_golf_course_tees_cat_gender")

    # Convert tee_category to VARCHAR first (remove new enum constraint)
    op.execute("ALTER TABLE golf_course_tees ALTER COLUMN tee_category TYPE VARCHAR(20)")
    op.execute("DROP TYPE IF EXISTS tee_category_enum")

    # Map FORWARD (new-only category) to JUNIOR (safe old value)
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'JUNIOR' "
        "WHERE tee_category = 'FORWARD'"
    )

    # Normalize NULL tee_gender: default to MALE for gendered categories
    op.execute(
        "UPDATE golf_course_tees SET tee_gender = 'MALE' "
        "WHERE tee_gender IS NULL AND tee_category IN ('CHAMPIONSHIP', 'AMATEUR', 'SENIOR')"
    )

    # Reconstruct combined legacy values from tee_category + tee_gender
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'CHAMPIONSHIP_MALE' "
        "WHERE tee_category = 'CHAMPIONSHIP' AND tee_gender = 'MALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'CHAMPIONSHIP_FEMALE' "
        "WHERE tee_category = 'CHAMPIONSHIP' AND tee_gender = 'FEMALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'AMATEUR_MALE' "
        "WHERE tee_category = 'AMATEUR' AND tee_gender = 'MALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'AMATEUR_FEMALE' "
        "WHERE tee_category = 'AMATEUR' AND tee_gender = 'FEMALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'SENIOR_MALE' "
        "WHERE tee_category = 'SENIOR' AND tee_gender = 'MALE'"
    )
    op.execute(
        "UPDATE golf_course_tees SET tee_category = 'SENIOR_FEMALE' "
        "WHERE tee_category = 'SENIOR' AND tee_gender = 'FEMALE'"
    )

    # Create old enum with 7 values and cast column
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
