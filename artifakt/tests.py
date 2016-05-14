import os
import unittest
from cgi import FieldStorage
from io import BytesIO
from tempfile import TemporaryDirectory

import transaction
from nose.tools import assert_in, assert_true
from pyramid import testing
from sqlalchemy.exc import OperationalError
from sqlalchemy.testing import eq_
from webob.multidict import MultiDict

from artifakt.models.models import DBSession
from artifakt.views.upload import upload_post


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
        from artifakt.models.models import (
            Base,
        )
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

