import json
import os
import unittest
from cgi import FieldStorage
from io import BytesIO
from tempfile import TemporaryDirectory

import transaction
from nose.tools import assert_in, assert_true, assert_raises, assert_is_not_none, \
    assert_false, assert_is_none, assert_greater
from pyramid import testing
from pyramid_fullauth.models import User
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.testing import eq_
from webob.multidict import MultiDict

from artifakt.models import models
from artifakt.models.models import Base
from artifakt.models.models import DBSession, Artifakt, Customer
from artifakt.utils.file import count_files
from artifakt.utils.time import duration_string
from artifakt.views.artifacts import artifact_delete, artifact_download, artifact_comment_add, artifact_delivery_add, \
    artifact_archive_view
from artifakt.views.upload import upload_post


# Enable to see SQL logs
# import logging
# log = logging.getLogger("sqlalchemy")
# log.addHandler(logging.StreamHandler())
# log.setLevel(logging.DEBUG)


# If you see a an error like: AttributeError: 'str' object has no attribute '__cause__'
# it's hiding the real exception since the logcapture plugin formats the error to a string
# Use --nologcapture to avoid this.

# TODO: Extract base class from setup/teardown

class TestMyViewSuccessCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from artifakt.models.models import (
            Base,
            Artifakt,
        )
        DBSession.remove()  # Must delete a session if it already exists
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            # noinspection PyArgumentList
            model = Artifakt(filename='one', sha1='deadbeef')
            DBSession.add(model)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_passing_view(self):
        from artifakt.views.artifacts import artifact
        request = testing.DummyRequest()
        request.matchdict['sha1'] = 'deadbeef'
        info = artifact(request)
        self.assertEqual(info['artifact'].filename, 'one')
        self.assertEqual(info['artifact'].sha1, 'deadbeef')


class TestMyViewFailureCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        DBSession.remove()  # Must delete a session if it already exists
        DBSession.configure(bind=engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_failing_view(self):
        from artifakt.views.artifacts import artifacts
        request = testing.DummyRequest()
        with self.assertRaises(OperationalError):
            artifacts(request)


class TestArtifact(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        self.engine = create_engine('sqlite://')
        DBSession.remove()  # Must delete a session if it already exists
        DBSession.configure(bind=self.engine)
        Base.metadata.create_all(self.engine)
        self.tmp_dir = TemporaryDirectory()
        models.storage = self.tmp_dir.name
        # All uploads needs a user
        self.user = User()
        self.user.username = "test"
        self.user.password = "1234"
        self.user.email = "a@b.cd"
        self.user.address_ip = "127.0.0.1"
        DBSession.add(self.user)
        DBSession.flush()

    def tearDown(self):
        testing.tearDown()
        transaction.abort()
        Base.metadata.drop_all(self.engine)

    def test_upload_no_file(self):
        request = testing.DummyRequest()
        response = upload_post(request)
        assert_in('error', response)
        eq_('Missing file field in POST request', response['error'])
        eq_(400, request.response.status_code)

    def generic_request(self, *args, **kwargs):
        request = testing.DummyRequest(*args, **kwargs)
        request.registry.settings['artifakt.storage'] = self.tmp_dir.name
        request.user = self.user
        return request

    def upload_request(self, files: dict, metadata=None):
        if metadata is None:
            metadata = '{}'
        fields = MultiDict({'metadata': metadata})
        for name, content in files.items():
            fs = FieldStorage()
            fs.file = BytesIO(content)
            fs.filename = name
            fields.add('file', fs)
        return self.generic_request(post=fields)

    def test_upload(self):
        # Upload a new file
        request = self.upload_request({'file.foo': b'foo'})
        response = upload_post(request)
        assert_in('artifacts', response)
        eq_(1, len(response['artifacts']))
        sha1 = response['artifacts'][0]
        eq_(200, request.response.status_code)
        target = os.path.join(self.tmp_dir.name, sha1[0:2], sha1[2:])
        assert_true(os.path.exists(target), target)
        assert_greater(os.path.getsize(target), 0)

        # Try the same again and we should get error
        request = self.upload_request({'file.foo': b'foo'})
        response = upload_post(request)
        assert_in('error', response)
        eq_('Artifact with sha1 {} already exists'.format(sha1), response['error'])
        eq_(409, request.response.status_code)

    def test_upload_with_metadata(self):
        metadata = {'artifakt': {'comment': 'test'},
                    'repository': {'url': 'r-url', 'name': 'r-name', 'type': 'git'},
                    'vcs': {'revision': '1'}}
        request = self.upload_request({'file.foo': b'foo'}, metadata=json.dumps(metadata))
        response = upload_post(request)
        assert_in('artifacts', response)
        eq_(1, len(response['artifacts']))
        sha1 = response['artifacts'][0]
        eq_(200, request.response.status_code)
        target = os.path.join(self.tmp_dir.name, sha1[0:2], sha1[2:])
        assert_true(os.path.exists(target), target)

        # Verify metadata
        af = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        eq_('file.foo', af.filename)
        eq_(sha1, af.sha1)
        eq_('test', af.comment)
        eq_(1, af.vcs_id)
        eq_(1, af.vcs.id)
        eq_('1', af.vcs.revision)
        eq_('r-url', af.vcs.repository.url)
        eq_('r-name', af.vcs.repository.name)
        assert_is_none(af.bundle_id)

    def test_upload_with_metadata_invalid(self):
        metadata = {'artifakt': {'comment': 'test'},
                    'repository': {'url': 'r-url', 'name': 'r-name'},
                    'vcs': {'revision': '1'}}
        request = self.upload_request({'file.foo': b'foo'}, metadata=json.dumps(metadata))
        assert_raises(IntegrityError, upload_post, request)
        DBSession.rollback()

        # Now there should be neither an artifakt object or a file
        eq_(0, count_files(self.tmp_dir.name))
        eq_(0, DBSession.query(Artifakt).count())

    def simple_upload(self):
        request = self.upload_request({'file.foo': b'foo'})
        upload_post(request)
        eq_(200, request.response.status_code)
        return DBSession.query(Artifakt).one()

    def test_upload_bundle(self):
        request = self.upload_request({'file.foo': b'foo', 'file.bar': b'bar'})
        upload_post(request)
        eq_(200, request.response.status_code)
        files = DBSession.query(Artifakt).all()
        eq_(3, len(files))  # Two files + the bundle itself
        eq_(None, files[0].bundle_id)
        assert_is_not_none(files[1].bundle_id)
        eq_(files[1].bundle_id, files[2].bundle_id)
        assert_true(all(a.uploader.username == 'test' for a in files))
        request = self.upload_request({'file.bin': b'bin', 'file.baz': b'baz'})
        upload_post(request)
        eq_(200, request.response.status_code)
        files = DBSession.query(Artifakt).all()
        eq_(6, len(files))  # 4 files + 2 bundles
        eq_(None, files[0].bundle_id)
        assert_is_not_none(files[1].bundle_id)
        eq_(files[1].bundle_id, files[2].bundle_id)
        eq_(None, files[3].bundle_id)
        assert_is_not_none(files[4].bundle_id)
        eq_(files[4].bundle_id, files[5].bundle_id)
        assert_true(all(a.uploader.username == 'test' for a in files))

    def test_delete(self):
        # Upload an artifact, and check that file exists
        af = self.simple_upload()
        assert_is_not_none(af)
        file_path = af.file
        assert_true(os.path.exists(file_path))
        # Now delete and verify that both file and artifact are deleted
        request = self.generic_request()
        request.matchdict.update({'sha1': af.sha1})
        artifact_delete(request)
        # FIXME: Investigate this: http://stackoverflow.com/a/23176618/11722
        transaction.commit()  # TODO: Better way to test this ? We must commit for the file to go away.
        assert_false(os.path.exists(file_path))
        assert_false(os.path.exists(os.path.dirname(file_path)))
        assert_is_none(DBSession.query(Artifakt).one_or_none())

    def test_download(self):
        af = self.simple_upload()
        request = testing.DummyRequest()
        request.matchdict.update({'sha1': af.sha1})
        response = artifact_download(request, inline=False)
        eq_(200, response.status_code)
        response = artifact_download(request, inline=True)
        eq_(200, response.status_code)
        # TODO: Verify downloaded file

    def test_add_comment(self):
        af = self.simple_upload()
        request = self.generic_request()
        json_comment = {'comment': 'test',
                        'artifakt_sha1': af.sha1,
                        'parent_id': None}
        setattr(request, 'json_body', json_comment)
        artifact_comment_add(request)
        eq_(af.comments[0].comment, 'test')
        eq_(len(af.root_comments), 1)
        json_comment['parent_id'] = af.comments[0].id
        json_comment['comment'] = 'test2'
        artifact_comment_add(request)
        DBSession.refresh(af)  # Or initial data is cached
        eq_(af.comments[1].comment, 'test2')
        eq_(len(af.root_comments), 1)

    def test_add_delivery(self):
        # Can't add delivery without a customer
        customer = Customer(name='Blargh')
        DBSession.add(customer)
        af = self.simple_upload()
        request = self.generic_request()
        json_delivery = {'comment': 'åäö',
                         'artifakt_sha1': af.sha1,
                         'target_id': customer.id,
                         'time': '1973-06-11'}
        setattr(request, 'json_body', json_delivery)
        artifact_delivery_add(request)
        eq_(1, len(af.deliveries))
        delivery = af.deliveries[0]
        eq_(delivery.artifakt_sha1, af.sha1)
        eq_(delivery.comment, 'åäö')
        eq_(delivery.to.name, customer.name)
        eq_(delivery.by.username, 'test')

    def test_archive_view(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(this_dir, 'test_data/foo.zip'), 'rb') as zipf:
            request = self.upload_request({'foo.zip': zipf.read()})
            response = upload_post(request)
            eq_(200, request.response.status_code)
            request = self.generic_request()
            request.matchdict['sha1'] = response['artifacts'][0]
            response = artifact_archive_view(request)
            eq_("Artifact archive: foo.zip", response['title'])
            eq_("foo", response['zipfiles'][0].filename)
            # TODO: Add tarfile test


class TestTime(unittest.TestCase):
    def test_zero(self):
        eq_(duration_string(0), '0 seconds')
