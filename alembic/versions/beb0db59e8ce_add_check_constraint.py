"""Add check constraint

Revision ID: beb0db59e8ce
Revises: 4c0d58a4687c
Create Date: 2017-04-26 11:40:55.834431

"""
from alembic import op
from artifakt.models.models import Repository

# revision identifiers, used by Alembic.
revision = 'beb0db59e8ce'
down_revision = '4c0d58a4687c'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.orm.session import Session
    session = Session(bind=op.get_bind())

    # Add dummy name where there is none
    for repo in session.query(Repository).all():
        if repo.name == "":
            repo.name = "NoName"
    session.commit()

    if session.bind.dialect.name == "sqlite":
        session.execute("PRAGMA foreign_keys = OFF")
    elif session.bind.dialect.name == "mysql":
        session.execute("SET foreign_key_checks = 0")
    else:
        raise NotImplemented

    with op.batch_alter_table('repository', schema=None) as batch_op:
        batch_op.create_check_constraint('non_empty_name', 'name != ""')

    if session.bind.dialect.name == "sqlite":
        session.execute("PRAGMA foreign_keys = ON")
    elif session.bind.dialect.name == "mysql":
        session.execute("SET foreign_key_checks = 1")


def downgrade():
    with op.batch_alter_table('repository', schema=None) as batch_op:
        batch_op.drop_constraint('non_empty_name')
