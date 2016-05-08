import logging
import os

from sqlalchemy import (
    Column,
    String,
    Text,
    CHAR,
    DateTime,
    event
    )
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )
from sqlalchemy.orm.session import object_session, Session
from sqlalchemy.sql import func
from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

# Set by main
# FIXME: Is there a better way ?
storage = None


class JSONSerializable(object):
    """Mixin for adding JSON serialization"""

    @staticmethod
    def convert(obj):
        """Makes sure some types can be json serialized"""
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        else:
            return obj

    def to_dict(self):
        # noinspection PyUnresolvedReferences
        return {c.name: self.convert(getattr(self, c.name)) for c in self.__table__.columns}


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)


class Artifakt(JSONSerializable, Base):
    __tablename__ = 'artifakt'
    sha1 = Column(CHAR(length=40), nullable=False, primary_key=True)
    filename = Column(String(length=255), nullable=False)
    comment = Column(Text)
    created = Column(DateTime, default=func.now())

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

    @staticmethod
    def metadata_keys():
        return ['comment']

    def _delete(self):
        """Called by events - should not be manually invoked"""
        file = self.file
        logging.getLogger(__name__).info("Deleting: " + file)
        if os.path.exists(file):
            os.remove(file)


# Would be nice if these could be inside the object instead ...

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
            obj._delete()
        deletes.clear()


# FIXME: Needed ?
# Index('my_index', Artifakt.name, unique=True, mysql_length=255)
