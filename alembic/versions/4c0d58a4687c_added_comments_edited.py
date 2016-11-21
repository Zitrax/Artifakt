"""Added comments.edited

Revision ID: 4c0d58a4687c
Revises: b5739a261104
Create Date: 2016-11-21 21:42:01.804309

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import false

revision = '4c0d58a4687c'
down_revision = 'b5739a261104'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('comment', sa.Column('edited', sa.Boolean(), server_default=false(), nullable=False))


def downgrade():
    op.drop_column('comment', 'edited')
