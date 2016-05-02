from sqlalchemy import (
    Column,
    Integer,
    String,
    CHAR
    )

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )

from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Artifakt(Base):
    __tablename__ = 'artifakt'
    id = Column(Integer, primary_key=True)
    filename = Column(String(length=255))
    sha1 = Column(CHAR(length=40))

# FIXME: Needed ?
# Index('my_index', Artifakt.name, unique=True, mysql_length=255)
