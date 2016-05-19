import json
import os
import unittest
from cgi import FieldStorage
from io import BytesIO
from tempfile import TemporaryDirectory

import transaction
from nose.tools import assert_in, assert_true, assert_raises, assert_is_not_none,\
    assert_false, assert_is_none, assert_greater
from pyramid import testing
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.testing import eq_
from webob.multidict import MultiDict

from artifakt.models import models
from artifakt.models.models import DBSession, Artifakt
from artifakt.utils.file import count_files
from artifakt.views.artifacts import artifact_delete, artifact_download
from artifakt.views.upload import upload_post


# Enable to see SQL logs
# import logging
# log = logging.getLogger("sqlalchemy")
# log.addHandler(logging.StreamHandler())
# log.setLevel(logging.DEBUG)


class TestMyViewSuccessCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from artifakt.models.models import (
            Base,
            Artifakt,
            )
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
        engine = create_engine('sqlite://')
        from artifakt.models.models import Base
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        self.tmp_dir = TemporaryDirectory()
        models.storage = self.tmp_dir.name

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_upload_no_file(self):
        request = testing.DummyRequest()
        response = upload_post(request)
        assert_in('error', response)
        eq_('Missing file field in POST request', response['error'])
        eq_(400, request.response.status_code)

    def generic_request(self, *args, **kwargs):
        request = testing.DummyRequest(*args, **kwargs)
        request.registry.settings['artifakt.storage'] = self.tmp_dir.name
        return request

    def upload_request(self, content, name, metadata=None):
        if metadata is None:
            metadata = '{}'
        fs = FieldStorage()
        fs.file = BytesIO(content)
        fs.filename = name
        fields = MultiDict({'file': fs, 'metadata': metadata})
        return self.generic_request(post=fields)

    def test_upload(self):
        # Upload a new file
        request = self.upload_request(b'foo', 'file.foo')
        response = upload_post(request)
        assert_in('artifacts', response)
        eq_(1, len(response['artifacts']))
        sha1 = response['artifacts'][0]
        eq_(200, request.response.status_code)
        target = os.path.join(self.tmp_dir.name, sha1[0:2], sha1[2:])
        assert_true(os.path.exists(target), target)
        assert_greater(os.path.getsize(target), 0)

        # Try the same again and we should get error
        request = self.upload_request(b'foo', 'file.foo')
        response = upload_post(request)
        assert_in('error', response)
        eq_('Artifact with sha1 {} already exists'.format(sha1), response['error'])
        eq_(409, request.response.status_code)

    def test_upload_with_metadata(self):
        metadata = {'artifakt': {'comment': 'test'},
                    'repository': {'url': 'r-url', 'name': 'r-name', 'type': 'git'},
                    'vcs': {'revision': '1'}}
        request = self.upload_request(b'foo', 'file.foo', metadata=json.dumps(metadata))
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

    def test_upload_with_metadata_invalid(self):
        metadata = {'artifakt': {'comment': 'test'},
                    'repository': {'url': 'r-url', 'name': 'r-name'},
                    'vcs': {'revision': '1'}}
        request = self.upload_request(b'foo', 'file.foo', metadata=json.dumps(metadata))
        assert_raises(IntegrityError, upload_post, request)
        DBSession.rollback()

        # Now there should be neither an artifakt object or a file
        eq_(0, count_files(self.tmp_dir.name))
        eq_(0, DBSession.query(Artifakt).count())

    def simple_upload(self):
        request = self.upload_request(b'foo', 'file.foo')
        upload_post(request)
        eq_(200, request.response.status_code)
        return DBSession.query(Artifakt).one()

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
