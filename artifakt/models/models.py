import logging
import mimetypes
import os
from datetime import datetime
from os.path import dirname

from artifakt.utils.file import count_files
from artifakt.utils.time import duration_string
from marshmallow import fields
from marshmallow_sqlalchemy import ModelSchema, ModelSchemaOpts
from pyramid_basemodel import Base, Session as DBSession
from pyramid_fullauth.models import User
from sqlalchemy import (
    Boolean,
    Column,
    CHAR,
    DateTime,
    event,
    Integer,
    ForeignKey,
    UniqueConstraint,
    Unicode,
    UnicodeText,
    Enum,
    CheckConstraint)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    relationship, backref)
from sqlalchemy.orm.session import object_session
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)

# Set by main
# FIXME: These should not be globals like this
__storage = None


def storage():
    return __storage


def set_storage(val):
    global __storage
    __storage = val


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


class UserSchema(BaseSchema):
    class Meta:
        model = User
        exclude = ['password']
        # TODO: Exclude more


schemas['user'] = UserSchema


# FIXME: Add cascading deletes


class Repository(Base):
    __tablename__ = 'repository'
    id = Column(Integer, nullable=False, autoincrement=True, primary_key=True)
    url = Column(Unicode(length=255), nullable=False, unique=True)
    name = Column(UnicodeText, CheckConstraint('name != ""', name="non_empty_name"))
    type = Column(Enum("git", "svn", name="type_enum"), nullable=False)

    def __str__(self):
        return self.name


class RepositorySchema(BaseSchema):
    class Meta:
        model = Repository


schemas['repository'] = RepositorySchema()


class Vcs(Base):
    __tablename__ = 'vcs'
    __table_args__ = (UniqueConstraint('repository_id', 'revision', name='rr'),)

    id = Column(Integer, nullable=False, autoincrement=True, primary_key=True)
    repository_id = Column(Integer, ForeignKey("repository.id"))
    revision = Column(CHAR(length=40), nullable=False)

    repository = relationship("Repository")

    def __str__(self):
        return "VCS({}, {}, {})".format(self.id, self.repository_id, self.revision)


class VcsSchema(BaseSchema):
    repository = fields.Nested(RepositorySchema, exclude=('id',))

    class Meta:
        model = Vcs


schemas['vcs'] = VcsSchema()


class Customer(Base):
    """Someone a delivery can be made to"""
    __tablename__ = "customer"
    id = Column(Integer, nullable=False, primary_key=True)
    name = Column(Unicode(length=255), nullable=False, unique=True)


class CustomerSchema(BaseSchema):
    class Meta:
        model = Customer


schemas['customer'] = CustomerSchema()


class Delivery(Base):
    """Represents a delivery of an artifakt to someone"""
    __tablename__ = "delivery"
    id = Column(Integer, nullable=False, primary_key=True)
    artifakt_sha1 = Column(CHAR(length=40), ForeignKey('artifakt.sha1'), nullable=False)
    comment = Column(UnicodeText)
    target_id = Column(Integer, ForeignKey('customer.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    time = Column(DateTime, default=func.now())

    to = relationship("Customer", backref=backref('deliveries', cascade="all, delete-orphan"))
    by = relationship("User", backref=backref('deliveries', cascade="all, delete-orphan"))


class DeliverySchema(BaseSchema):
    to = fields.Nested(CustomerSchema)
    by = fields.Nested(UserSchema, only=['username'])

    class Meta:
        model = Delivery


schemas['delivery'] = DeliverySchema()


class Artifakt(Base):
    """One artifact is one or several files.

    Each artifact can be part of a bundle, a bundle is several grouped artifacts.
    For example part of a software release.
    """
    __tablename__ = 'artifakt'
    sha1 = Column(CHAR(length=40), nullable=False, primary_key=True)
    filename = Column(Unicode(length=255), nullable=True)
    comment = Column(UnicodeText)
    created = Column(DateTime, default=func.now())
    uploaded_by = Column(Integer, ForeignKey('users.id'))
    vcs_id = Column(Integer, ForeignKey(Vcs.id))
    is_bundle = Column(Boolean, default=False)
    keep_alive = Column(Boolean, default=True)

    vcs = relationship(Vcs)
    # This must be viewonly or we will get problems with the vcs relationship ( #56 )
    repository = relationship("Repository", secondary='vcs', backref='artifacts', viewonly=True)
    bundles = relationship("Artifakt", secondary='bundle_link', backref='artifacts',
                           primaryjoin='BundleLink.artifact_sha1 == Artifakt.sha1',
                           secondaryjoin='BundleLink.bundle_sha1 == Artifakt.sha1')
    uploader = relationship("User", backref=backref('artifacts', cascade="all, delete-orphan"))
    deliveries = relationship(Delivery, backref='artifakt', cascade="all, delete-orphan")

    def bundle_filename(self, bundle):
        """Return the filename for this artifact in a specific bundle

        An artifact always has the original filename. However if it's part
        of a bundle the bundle may have a different filename for the same
        artifact.
        """
        if self.is_bundle:
            raise ValueError("This is a bundle")
        for al in self.bundle_links:
            if al.bundle == bundle:
                return al.filename if al.filename else self.filename
        raise ValueError("Artifact not in bundle")

    @property
    def name(self):
        return self.filename or self.sha1

    @name.setter
    def name(self, value):
        self.filename = value

    @property
    def root_comments(self):
        return [c for c in self.comments if c.parent_id is None]

    @property
    def age(self):
        return duration_string((datetime.utcnow() - self.created).total_seconds())

    @property
    def file(self):
        if self.is_bundle:
            return os.path.join(storage(), 'zip', self.sha1 + '.zip')
        else:
            return os.path.join(storage(), self.sha1[0:2], self.sha1[2:])

    @property
    def size(self):
        # TODO: Possibly it's better to store this in the db - since size should not change anyway
        try:
            if self.is_bundle:
                return sum(a.size for a in self.artifacts)
            else:
                return os.path.getsize(self.file)
        except FileNotFoundError:
            return 0

    @property
    def exists(self):
        return os.path.exists(self.file)

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
        mime, encoding = mimetypes.guess_type(self.filename, strict=False)
        return mime

    @property
    def is_archive(self):
        return self.mime in ['application/x-tar', 'application/zip', 'application/x-zip-compressed',
                             'application/x-7z-compressed']

    @property
    def is_text(self):
        return self.mime in ['text/plain']

    @staticmethod
    def metadata_keys():
        # TODO: Extract this automatically along with types
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


# Link table telling which artifacts belong to which bundles
class BundleLink(Base):
    __tablename__ = 'bundle_link'

    artifact_sha1 = Column(CHAR(length=40), ForeignKey('artifakt.sha1'), primary_key=True)
    bundle_sha1 = Column(CHAR(length=40), ForeignKey('artifakt.sha1'), primary_key=True)
    filename = Column(Unicode(length=255), nullable=False)

    bundle = relationship(Artifakt, backref=backref("artifact_links", cascade="all, delete-orphan"),
                          foreign_keys=bundle_sha1)
    artifact = relationship(Artifakt, backref=backref("bundle_links", cascade="all, delete-orphan"),
                            foreign_keys=artifact_sha1)

    def __repr__(self):
        return "{} -> {} ({})".format(self.bundle_sha1[:4], self.artifact_sha1[:4], self.filename)


class ArtifaktSchema(BaseSchema):
    vcs = fields.Nested(VcsSchema, exclude=('id',))

    class Meta:
        model = Artifakt


schemas['artifakt'] = ArtifaktSchema()


class Comment(Base):
    __tablename__ = 'comment'
    id = Column(Integer, nullable=False, primary_key=True)
    artifakt_sha1 = Column(CHAR(length=40), ForeignKey('artifakt.sha1'), nullable=False)
    comment = Column(UnicodeText, nullable=False)
    time = Column(DateTime, default=func.now())
    user_id = Column(Integer, ForeignKey('users.id'))
    parent_id = Column(Integer, ForeignKey('comment.id'), nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)
    edited = Column(Boolean, default=False, nullable=False)

    artifakt = relationship('Artifakt', backref=backref('comments', cascade="all, delete-orphan"))
    user = relationship('User')
    parent = relationship('Comment', backref=backref('replies', cascade="all, delete-orphan"), remote_side='Comment.id')

    @property
    def age(self):
        return duration_string((datetime.utcnow() - self.time).total_seconds())

    def delete(self):
        # If the comment has replies it will only marked as deleted
        if len(self.replies):
            self.comment = "<DELETED>"
            self.deleted = True
        # If note it will fully deleted
        else:
            DBSession.delete(self)

    @property
    def parents(self):
        """All parent comments in this thread"""
        parents = set()
        p = self
        while p.parent:
            parents.add(p.parent)
            p = p.parent
        return parents


class CommentSchema(BaseSchema):
    user = fields.Nested(UserSchema, only=['username'])
    age = fields.Method(serialize='get_age')

    # TODO: See if we really need fields.Method
    def get_age(self, obj):
        return obj.age

    class Meta:
        model = Comment


schemas['comment'] = CommentSchema()


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


@event.listens_for(DBSession, 'before_flush')
def artifakt_before_flush(session, *_):
    """When deleting a bundle certain contained artifacts should also be deleted"""
    for obj in session.deleted:
        if type(obj) is Artifakt:
            if obj.is_bundle:
                for af in obj.artifacts:
                    if not set(af.bundles) - {obj}:  # If the artifact would not be in a bundle anymore
                        if not af.keep_alive:
                            DBSession.delete(af)
            else:  # Safety checks. We try to prevent reaching this in the views.
                if obj.bundles:
                    raise ValueError("Won't delete {} (belongs to bundle)".format(obj.sha1))


@event.listens_for(DBSession, 'after_rollback')
def artifakt_after_rollback(session):
    """Clear list of targets to delete"""
    if hasattr(session, 'deletes'):
        getattr(session, 'deletes').clear()


@event.listens_for(DBSession, 'after_commit')
def artifakt_after_commit(session):
    """Call delete to actually delete the associated files"""
    deletes = getattr(session, 'deletes', None)
    if deletes:
        for obj in deletes:
            # noinspection PyProtectedMember
            obj._delete()
        deletes.clear()


# noinspection PyUnusedLocal
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """This ensures that SQLite enforce the use of foreign keys"""
    from sqlite3 import Connection as SQLite3Connection
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

# FIXME: Needed ?
# Index('my_index', Artifakt.name, unique=True, mysql_length=255)
