import unittest

import transaction
from pyramid import testing
from sqlalchemy.exc import OperationalError

from artifakt.models.models import DBSession


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