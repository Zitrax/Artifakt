"""vcs unique constraint

Revision ID: b5739a261104
Revises: 
Create Date: 2016-11-04 21:39:28.316494

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from artifakt.models.models import Vcs, Artifakt
from sqlalchemy import func

revision = 'b5739a261104'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.orm.session import Session
    session = Session(bind=op.get_bind())

    # Find duplicates
    for vcs in session.query(Vcs).group_by(Vcs.repository_id, Vcs.revision).having(func.count(Vcs.id) > 1).all():
        print(vcs)
        # Find all vcs entries with this duplication
        dupes = session.query(Vcs).filter(Vcs.repository_id == vcs.repository_id).filter(Vcs.revision == vcs.revision).all()
        # Keep the first and remove the others - thus we need to update references to others to the first
        for update in dupes[1:]:
            for af in session.query(Artifakt).filter(Artifakt.vcs_id == update.id).all():
                print("Updating artifakt {} to point to vcs {}".format(af.sha1, dupes[0].id))
                af.vcs_id = dupes[0].id
            print("Deleting vcs  {}".format(update.id))
            session.delete(update)
    session.commit()

    if session.bind.dialect.name == "sqlite":
        session.execute("PRAGMA foreign_keys = OFF")
    elif session.bind.dialect.name == "mysql":
        session.execute("SET foreign_key_checks = 0")
    else:
        raise NotImplemented

    with op.batch_alter_table('vcs', schema=None) as batch_op:
        batch_op.create_unique_constraint('rr', ['repository_id', 'revision'])

    if session.bind.dialect.name == "sqlite":
        session.execute("PRAGMA foreign_keys = ON")
    elif session.bind.dialect.name == "mysql":
        session.execute("SET foreign_key_checks = 1")


def downgrade():
    with op.batch_alter_table('vcs', schema=None) as batch_op:
        batch_op.drop_constraint('rr', type_='unique')
