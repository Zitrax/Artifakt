import logging
import mimetypes
import os
from os.path import dirname

from marshmallow import fields
from marshmallow_sqlalchemy import ModelSchema, ModelSchemaOpts
from sqlalchemy import (
    Column,
    CHAR,
    DateTime,
    event,
    Integer,
    ForeignKey,
    UniqueConstraint,
    Unicode,
    UnicodeText,
    Enum
    )
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship)
from sqlalchemy.orm.session import object_session, Session
from sqlalchemy.sql import func
from zope.sqlalchemy import ZopeTransactionExtension

from artifakt.utils.file import count_files

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()
logger = logging.getLogger(__name__)

# Set by main
# FIXME: Is there a better way ?
storage = None


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


class BaseOpts(ModelSchemaOpts):
    def __init__(self, meta):
        if not hasattr(meta, 'sql_session'):
            meta.sqla_session = DBSession
        super(BaseOpts, self).__init__(meta)


class BaseSchema(ModelSchema):
    OPTIONS_CLASS = BaseOpts


schemas = {}

# FIXME: Add cascading deletes


class Repository(Base):
    __tablename__ = 'repository'
    id = Column(Integer, nullable=False, autoincrement=True, primary_key=True)
    url = Column(Unicode(length=255), nullable=False, unique=True)
    name = Column(UnicodeText)
    type = Column(Enum("git", "svn", name="type_enum"), nullable=False)


class RepositorySchema(BaseSchema):
    class Meta:
        model = Repository


schemas['repository'] = RepositorySchema()


class Vcs(Base):
    __tablename__ = 'vcs'
    id = Column(Integer, nullable=False, autoincrement=True, primary_key=True)
    repository_id = Column(Integer, ForeignKey("repository.id"))
    revision = Column(CHAR(length=40), nullable=False)

    UniqueConstraint('repository_id', 'revision', name='rr')

    repository = relationship("Repository")


class VcsSchema(BaseSchema):
    repository = fields.Nested(RepositorySchema, exclude=('id',))

    class Meta:
        model = Vcs


schemas['vcs'] = VcsSchema()


class Artifakt(Base):
    __tablename__ = 'artifakt'
    sha1 = Column(CHAR(length=40), nullable=False, primary_key=True)
    filename = Column(Unicode(length=255), nullable=False)
    comment = Column(UnicodeText)
    created = Column(DateTime, default=func.now())
    vcs_id = Column(Integer, ForeignKey("vcs.id"))

    vcs = relationship("Vcs")

    @property
    def file(self):
        return os.path.join(storage, self.sha1[0:2], self.sha1[2:])

    @property
    def size(self):
        # TODO: Possibly it's better to store this in the db - since size should not change anyway
        return os.path.getsize(self.file)

    @property
    def file_content(self):
        with open(self.file, errors='replace') as f:
            return f.read()

    @property
    def size_h(self):
        """Human readable size"""
        return sizeof_fmt(self.size)

    @property
    def mime(self):
        mime, encoding = mimetypes.guess_type(self.filename)
        return mime

    @property
    def is_archive(self):
        # FIXME: Do not duplicate this and in the view
        return self.mime in ['application/x-tar', 'application/zip', 'application/x-zip-compressed']

    @staticmethod
    def metadata_keys():
        # TODO: Extract ths automatically along with types
        return {'artifakt': ['comment'],
                'repository': ['url', 'name', 'type'],
                'vcs': ['revision']}

    def _delete(self):
        """Called by events - should not be manually invoked"""
        file = self.file
        logger.info("Deleting: " + file)
        if os.path.exists(file):
            os.remove(file)
            tdir = dirname(file)
            # FIXME: Tiny risk of deleting this dir while another upload tries to use it
            if count_files(tdir) == 0:
                logger.info("Deleting: " + tdir)
                os.rmdir(tdir)


class ArtifaktSchema(BaseSchema):
    vcs = fields.Nested(VcsSchema, exclude=('id',))

    class Meta:
        model = Artifakt

schemas['artifakt'] = ArtifaktSchema()


# Would be nice if these could be inside the object instead ...

# noinspection PyUnusedLocal
@event.listens_for(Artifakt, 'after_delete')
def artifakt_after_delete(mapper, connection, target):
    """Register a delete on the target

    The delete might or might not be committed - so we can't perform any changes now.
    """
    session = object_session(target)
    if not hasattr(session, 'deletes'):
        setattr(session, 'deletes', [target])
    else:
        getattr(session, 'deletes').append(target)


@event.listens_for(Session, 'after_rollback')
def artifakt_after_rollback(session):
    """Clear list of targets to delete"""
    if hasattr(session, 'deletes'):
        getattr(session, 'deletes').clear()


@event.listens_for(Session, 'after_commit')
def artifakt_after_commit(session):
    """Call delete to actually delete the associated files"""
    deletes = getattr(session, 'deletes', None)
    if deletes:
        for obj in deletes:
            # noinspection PyProtectedMember
            obj._delete()
        deletes.clear()


# FIXME: Needed ?
# Index('my_index', Artifakt.name, unique=True, mysql_length=255)
