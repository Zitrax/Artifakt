from sqlalchemy import (
    Column,
    String,
    Text,
    CHAR,
    DateTime
    )
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )
from sqlalchemy.sql import func
from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class JSONSerializable(object):
    """Mixin for adding JSON serialization"""
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Artifakt(JSONSerializable, Base):
    __tablename__ = 'artifakt'
    sha1 = Column(CHAR(length=40), nullable=False, primary_key=True)
    filename = Column(String(length=255), nullable=False)
    comment = Column(Text)
    created = Column(DateTime, default=func.now())



# FIXME: Needed ?
# Index('my_index', Artifakt.name, unique=True, mysql_length=255)
