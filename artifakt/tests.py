import json
import os
import unittest
from cgi import FieldStorage
from io import BytesIO
from tempfile import TemporaryDirectory

import transaction
from nose.tools import assert_in, assert_true, assert_raises
from pyramid import testing
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.testing import eq_
from webob.multidict import MultiDict

from artifakt.models.models import DBSession, Artifakt
from artifakt.views.upload import upload_post


# Enable to see SQL logs
#import logging
#log = logging.getLogger("sqlalchemy")
#log.addHandler(logging.StreamHandler())
#log.setLevel(logging.DEBUG)


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


class TestUpload(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from artifakt.models.models import Base
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        self.tmp_dir = TemporaryDirectory()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_upload_no_file(self):
        request = testing.DummyRequest()
        response = upload_post(request)
        assert_in('error', response)
        eq_('Missing file field in POST request', response['error'])
        eq_(400, request.response.status_code)

    def upload_request(self, content, name, metadata=None):
        if metadata is None:
            metadata = '{}'
        fs = FieldStorage()
        fs.file = BytesIO(content)
        fs.filename = name
        fields = MultiDict({'file': fs, 'metadata': metadata})
        request = testing.DummyRequest(post=fields)
        request.registry.settings['artifakt.storage'] = self.tmp_dir.name
        return request

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
        def count_files(path):
            x = 0
            for root, dirs, files in os.walk(path):
                x += len(files)
            return x

        eq_(0, count_files(self.tmp_dir.name))
        eq_(0, DBSession.query(Artifakt).count())
