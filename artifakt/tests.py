import json
import os
import unittest
from cgi import FieldStorage
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest import skip
from unittest.mock import patch

import transaction
from nose.tools import assert_in, assert_true, assert_raises, assert_is_not_none, \
    assert_false, assert_is_none, assert_greater, assert_list_equal
from nose.tools import assert_set_equal
from pyramid import testing
from pyramid.httpexceptions import HTTPForbidden, HTTPBadRequest
from pyramid_fullauth.models import User
from pyramid_mailer import get_mailer
from sqlalchemy import desc
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.testing import eq_
from webob.multidict import MultiDict

from artifakt.models import models
from artifakt.models.models import Base, Delivery, Comment, BundleLink
from artifakt.models.models import DBSession, Artifakt, Customer
from artifakt.utils.file import count_files
from artifakt.utils.time import duration_string
from artifakt.views.admin import admin, verify_fs
from artifakt.views.artifacts import artifact_delete, artifact_download, artifact_comment_add, artifact_delivery_add, \
    artifact_archive_view, artifact_delivery_delete, artifacts_json, artifact_json, artifact_comment_edit, \
    artifact_comment_delete
from artifakt.views.artifacts import artifacts
from artifakt.views.search import search
from artifakt.views.upload import upload_post


# Enable to see SQL logs
# import logging
# log = logging.getLogger("sqlalchemy")
# log.addHandler(logging.StreamHandler())
# log.setLevel(logging.DEBUG)


# If you see a an error like: AttributeError: 'str' object has no attribute '__cause__'
# it's hiding the real exception since the logcapture plugin formats the error to a string
# Use --nologcapture to avoid this.


class BaseTest(unittest.TestCase):
    def setUp(self, create=True):
        self.config = testing.setUp()
        self.config.include('pyramid_mailer.testing')
        from sqlalchemy import create_engine
        self.engine = create_engine('sqlite://')
        DBSession.remove()  # Must delete a session if it already exists
        DBSession.configure(bind=self.engine)
        if create:
            Base.metadata.create_all(self.engine)
            self.tmp_dir = TemporaryDirectory()
            models.set_storage(self.tmp_dir.name)
            zip_dir = os.path.join(models.storage(), 'zip')
            if not os.path.exists(zip_dir):
                os.mkdir(zip_dir)
            # All uploads needs a user
            self.user = User()
            self.user.username = "test"
            self.user.password = "1234"
            self.user.email = "a@b.cd"
            self.user.address_ip = "127.0.0.1"
            DBSession.add(self.user)

            # And one more such that we can test interaction between users
            self.user2 = User()
            self.user2.username = "test2"
            self.user2.password = "1234"
            self.user2.email = "x@y.zz"
            self.user2.address_ip = "127.0.0.1"
            DBSession.add(self.user2)

            DBSession.flush()

    def tearDown(self):
        testing.tearDown()
        transaction.abort()
        Base.metadata.drop_all(self.engine)

    def generic_request(self, *args, **kwargs):
        request = testing.DummyRequest(*args, **kwargs)
        request.registry.settings['artifakt.storage'] = self.tmp_dir.name
        request.user = kwargs['user'] if 'user' in kwargs else self.user
        if 'url' in kwargs:
            request.url = kwargs['url']
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

    def simple_upload(self, content=None, expected_status=200):
        if content is None:
            content = {'file.foo': b'foo'}
        request = self.upload_request(content)
        res = upload_post(request)
        eq_(expected_status, request.response.status_code)
        return DBSession.query(Artifakt).filter(Artifakt.sha1 == res['artifacts'][0]).one()

    def delete_artifact(self, af):
        request = self.generic_request()
        request.matchdict.update({'sha1': af.sha1})
        artifact_delete(request)


class TestMyViewSuccessCondition(BaseTest):
    def setUp(self, **kwargs):
        super(TestMyViewSuccessCondition, self).setUp()
        with transaction.manager:
            # noinspection PyArgumentList
            model = Artifakt(filename='one', sha1='deadbeef' * 5)
            DBSession.add(model)

    def test_passing_view(self):
        from artifakt.views.artifacts import artifact
        request = testing.DummyRequest()
        request.matchdict['sha1'] = 'deadbeef' * 5
        info = artifact(request)
        self.assertEqual(info['artifact'].filename, 'one')
        self.assertEqual(info['artifact'].sha1, 'deadbeef' * 5)


class TestMyViewFailureCondition(BaseTest):
    def setUp(self, **kwargs):
        super(TestMyViewFailureCondition, self).setUp(create=False)

    def test_failing_view(self):
        request = testing.DummyRequest()
        with self.assertRaises(OperationalError):
            artifacts(request)


class TestArtifact(BaseTest):
    def test_upload_no_file(self):
        request = testing.DummyRequest()
        response = upload_post(request)
        assert_in('error', response)
        eq_('Missing file field in POST request', response['error'])
        eq_(400, request.response.status_code)

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

        # Try the same again and we should get 302
        request = self.upload_request({'file.foo': b'foo'})
        upload_post(request)
        eq_(302, request.response.status_code)

    def upload_with_metadata(self, metadata=None):
        if metadata is None:
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
        return sha1

    def test_upload_with_metadata(self):
        sha1 = self.upload_with_metadata()
        # Verify metadata
        af = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        eq_('file.foo', af.filename)
        eq_(sha1, af.sha1)
        eq_('test', af.comment)
        eq_(1, af.vcs_id)
        eq_('1', af.vcs.revision)
        eq_('r-url', af.vcs.repository.url)
        eq_('r-name', af.vcs.repository.name)

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

    def test_upload_delete_upload(self):
        # Verify fix for #77
        # Upload with metadata, delete and upload the same file again
        sha1 = self.upload_with_metadata()
        af = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        self.delete_artifact(af)
        transaction.commit()  # Must commit for the file on disk to go away
        sha1 = self.upload_with_metadata()
        # Verify metadata
        af = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        eq_('file.foo', af.filename)
        eq_(sha1, af.sha1)
        eq_('test', af.comment)
        eq_(1, af.vcs_id)
        eq_('1', af.vcs.revision)
        eq_('r-url', af.vcs.repository.url)
        eq_('r-name', af.vcs.repository.name)

    def test_upload_repository_no_revision(self):
        metadata = {'artifakt': {'comment': 'test'},
                    'repository': {'url': 'r-url', 'name': 'r-name', 'type': 'git'}}
        sha1 = self.upload_with_metadata(metadata=metadata)
        # Verify metadata
        af = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        eq_('file.foo', af.filename)
        eq_(sha1, af.sha1)
        eq_('test', af.comment)
        assert_is_not_none(af.vcs)
        eq_(1, af.vcs_id)
        eq_('r-url', af.vcs.repository.url)
        eq_('r-name', af.vcs.repository.name)

    def test_upload_no_repository_no_revision(self):
        metadata = {'artifakt': {'comment': 'test'}}
        sha1 = self.upload_with_metadata(metadata=metadata)
        # Verify metadata
        af = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        eq_('file.foo', af.filename)
        eq_(sha1, af.sha1)
        eq_('test', af.comment)
        assert_is_none(af.vcs)
        assert_is_none(af.vcs_id)

    def upload_bundle(self, files, expected_status=200, metadata=None):
        request = self.upload_request(files, metadata=metadata)
        upload_post(request)
        eq_(expected_status, request.response.status_code)

    def test_upload_bundle(self):
        self.upload_bundle({'file.foo': b'foo', 'file.bar': b'bar'})
        files = DBSession.query(Artifakt).order_by(desc(Artifakt.is_bundle)).all()
        eq_(3, len(files))  # Two files + the bundle itself
        assert_list_equal([f.is_bundle for f in files], [True, False, False])
        assert_list_equal([len(f.bundles) for f in files], [0, 1, 1])
        eq_(1, len(files[1].bundles))
        eq_(files[1].bundles, files[2].bundles)
        assert_true(all(a.uploader.username == 'test' for a in files))
        self.upload_bundle({'file.bin': b'bin', 'file.baz': b'baz'})
        files = DBSession.query(Artifakt).all()
        files = sorted(files, key=lambda f: f.bundles[0].sha1 if f.bundles else '')
        eq_(6, len(files))  # 4 files + 2 bundles
        assert_list_equal([f.is_bundle for f in files], [True, True, False, False, False, False])
        assert_list_equal([len(f.bundles) for f in files], [0, 0, 1, 1, 1, 1])
        eq_(1, len(files[2].bundles))
        assert_list_equal(files[2].bundles, files[3].bundles)
        eq_(1, len(files[4].bundles))
        assert_list_equal(files[4].bundles, files[5].bundles)
        assert_true(all(a.uploader.username == 'test' for a in files))

    @skip("Fix - the 409 is no longer valid. Should inject fault somehow")
    def test_upload_bundle_fail(self):
        self.upload_bundle({'aa': b'aa', 'bb': b'bb'})
        # This bundle will fail since bb already exists - should not leave cc on the server
        self.upload_bundle({'cc': b'cc', 'bb': b'bb', 'dd': b'dd'}, expected_status=409)
        files = DBSession.query(Artifakt).filter(~Artifakt.is_bundle).all()
        self.assertCountEqual([f.filename for f in files], ['aa', 'bb'])
        DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()

    # Mocking away this function means we will throw IntegrityError
    @patch('artifakt.views.upload.prepare_repo')
    def test_bundle_with_vcs_info_fail(self, _):
        metadata = {'vcs': {'revision': '1'},
                    'repository': {'url': 'a', 'name': 'b', 'type': 'git'},
                    'artifakt': {'comment': 'hej'}}
        assert_raises(IntegrityError, self.upload_bundle, {'foo': b'foo', 'bar': b'bar'}, metadata=json.dumps(metadata))
        DBSession.rollback()
        eq_(0, DBSession.query(Artifakt).count())
        request = self.generic_request()
        request.registry.settings['mail.queue_path'] = 'maildir'
        info = verify_fs(request)
        assert_list_equal([], info['not_on_disk'])
        assert_list_equal([], info['not_in_db'])

    # Make sure upload does not remove files already in the db on failure
    def test_bundle_fail_existing_files(self):
        self.upload_bundle({'aa': b'aa', 'bb': b'bb'})
        transaction.commit()
        # User needs to be reused so refetch it. Unsure why DBSession.refresh is not working
        self.user = DBSession.query(User).filter(User.id == 1).one()

        with patch('artifakt.views.upload.prepare_repo') as repo_mock:
            repo_mock.side_effect = Exception("Ugh")
            assert_raises(Exception, self.upload_bundle, {'aa': b'aa', 'bb': b'bb', 'cc': b'cc'})
            DBSession.rollback()

        eq_(3, DBSession.query(Artifakt).count())
        files = DBSession.query(Artifakt).all()
        self.assertCountEqual([f.filename for f in files], [None, 'aa', 'bb'])
        request = self.generic_request()
        request.registry.settings['mail.queue_path'] = 'maildir'
        info = verify_fs(request)
        assert_list_equal([], info['not_on_disk'])
        assert_list_equal([], info['not_in_db'])

    def test_bundle_duplicate_content(self):
        self.upload_bundle({'aa': b'aa', 'bb': b'bb'})
        self.upload_bundle({'AA': b'aa', 'cc': b'cc'})
        b1 = DBSession.query(Artifakt).filter(Artifakt.filename == 'bb').one().bundles[0]
        b2 = DBSession.query(Artifakt).filter(Artifakt.filename == 'cc').one().bundles[0]
        assert_set_equal(set(a.filename for a in b1.artifacts), {'aa', 'bb'})  # Fixed filenames
        assert_set_equal(set(a.bundle_filename(b1) for a in b1.artifacts), {'aa', 'bb'})  # Bundle filenames
        assert_set_equal(set(a.bundle_filename(b2) for a in b2.artifacts), {'AA', 'cc'})  # Bundle filenames
        assert_set_equal(set(a.filename for a in b2.artifacts), {'aa', 'cc'})  # Fixed filenames

        # Delete bundles and check that links are removed
        eq_(4, DBSession.query(BundleLink).count())  # One link per artifact
        DBSession.delete(b1)
        DBSession.delete(b2)
        transaction.commit()
        eq_(0, DBSession.query(BundleLink).count())

    def test_bundle_with_vcs_info(self):
        metadata = {'vcs': {'revision': '1'},
                    'repository': {'url': 'a', 'name': 'b', 'type': 'git'},
                    'artifakt': {'comment': 'hej'}}
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'}, metadata=json.dumps(metadata))
        files = DBSession.query(Artifakt).all()
        self.assertCountEqual(['hej', 'foo', 'bar'], [f.filename for f in files])
        files = DBSession.query(Artifakt).filter(~Artifakt.is_bundle).all()
        self.assertCountEqual(['b', 'b'], [f.vcs.repository.name for f in files])
        self.assertCountEqual(['a', 'a'], [f.vcs.repository.url for f in files])
        self.assertCountEqual(['git', 'git'], [f.vcs.repository.type for f in files])
        self.assertCountEqual(['1', '1'], [f.vcs.revision for f in files])
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        eq_('b', bundle.vcs.repository.name)
        eq_('a', bundle.vcs.repository.url)
        eq_('git', bundle.vcs.repository.type)
        eq_('1', bundle.vcs.revision)

    def test_upload_bundle_cascading(self):
        self.upload_bundle({'file.foo': b'foo', 'file.bar': b'bar'})
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        files = [af.file for af in DBSession.query(Artifakt).all()]
        DBSession.delete(bundle)
        eq_([], DBSession.query(Artifakt).all())
        transaction.commit()  # TODO: Better way to test this ? We must commit for the file to go away.
        assert_true(all(not os.path.exists(file) for file in files))

    def test_bundle_delete_advanced(self):
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'})
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        eq_(3, DBSession.query(Artifakt).count())  # One bundle and two files
        self.upload_bundle({'bar': b'bar', 'baz': b'baz'})
        eq_(5, DBSession.query(Artifakt).count())  # Two bundles and the three common files
        # Delete first bundle. It should delete the not common file foo but keep the common bar
        DBSession.delete(bundle)
        transaction.commit()  # Must commit here such that the delete takes full effect before handling the next
        files = DBSession.query(Artifakt).all()
        self.assertCountEqual([None, 'bar', 'baz'], [f.filename for f in files])
        # Now upload baz manually - it should mark it as keep alive
        self.simple_upload({'baz': b'baz'}, expected_status=302)
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        DBSession.delete(bundle)
        # Now the bundle and bar should be gone
        files = DBSession.query(Artifakt).all()
        self.assertCountEqual(['baz'], [f.filename for f in files])

    def test_delete(self):
        # Upload an artifact, and check that file exists
        af = self.simple_upload()
        assert_is_not_none(af)
        file_path = af.file
        assert_true(os.path.exists(file_path))
        # Now delete and verify that both file and artifact are deleted
        self.delete_artifact(af)
        # FIXME: Investigate this: http://stackoverflow.com/a/23176618/11722
        transaction.commit()  # TODO: Better way to test this ? We must commit for the file to go away.
        assert_false(os.path.exists(file_path))
        assert_false(os.path.exists(os.path.dirname(file_path)))
        assert_is_none(DBSession.query(Artifakt).one_or_none())

    def test_delete_bundle_file(self):
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'})
        af = DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()
        assert_raises(HTTPForbidden, self.delete_artifact, af)
        # The file belong to a bundle and should thus not be deleted
        DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()
        # Delete the bundle - it should make the file go away.
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        self.delete_artifact(bundle)
        transaction.commit()
        assert_is_none(DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one_or_none())

    def test_delete_bundle_file_loner(self):
        # Upload a lone file and then the same file in a bundle. Such a file should stay.
        self.simple_upload({'foo': b'foo'})
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'})
        af = DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()
        assert_raises(HTTPForbidden, self.delete_artifact, af)
        # The file belong to a bundle and should thus not be deleted
        DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()
        # Delete the bundle - it should not make the file go away.
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        self.delete_artifact(bundle)
        transaction.commit()
        DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()

    def test_delete_bundle_file_loner_reverse(self):
        # Upload a lone file and then the same file in a bundle. Such a file should stay.
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'})
        self.simple_upload({'foo': b'foo'}, expected_status=302)
        af = DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()
        assert_raises(HTTPForbidden, self.delete_artifact, af)
        # The file belong to a bundle and should thus not be deleted
        DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()
        # Delete the bundle - it should not make the file go away.
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        self.delete_artifact(bundle)
        transaction.commit()
        DBSession.query(Artifakt).filter(Artifakt.filename == 'foo').one()

    def test_delete_bundle_vcs_info(self):
        metadata = {'vcs': {'revision': '1'},
                    'repository': {'url': 'a', 'name': 'b', 'type': 'git'},
                    'artifakt': {'comment': 'hej'}}
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'}, metadata=json.dumps(metadata))
        bundle = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        self.delete_artifact(bundle)
        transaction.commit()
        eq_([], DBSession.query(Artifakt).filter(Artifakt.is_bundle).all())

    def test_bundle_download(self):
        self.upload_bundle({'foo': b'foo', 'bar': b'bar'})
        af = DBSession.query(Artifakt).filter(Artifakt.is_bundle).one()
        request = testing.DummyRequest()
        request.matchdict.update({'sha1': af.sha1})
        response = artifact_download(request, inline=False)
        eq_(200, response.status_code)
        assert_raises(HTTPBadRequest, artifact_download, request, inline=True)
        # TODO: Verify downloaded file

    def test_download(self):
        af = self.simple_upload()
        request = testing.DummyRequest()
        request.matchdict.update({'sha1': af.sha1})
        response = artifact_download(request, inline=False)
        eq_(200, response.status_code)
        response = artifact_download(request, inline=True)
        eq_(200, response.status_code)
        # TODO: Verify downloaded file

    def add_comment(self, reply=True, mail_count=0, user=None, parent_id=None, af=None):
        if user is None:
            user = self.user
        if af is None:
            af = self.simple_upload()
        request = self.generic_request(user=user, url='http://example.com:1234/artifact/deadbeef/comment')
        json_comment = {'comment': 'test',
                        'artifakt_sha1': af.sha1,
                        'parent_id': parent_id,
                        'user_id': user.id}
        setattr(request, 'json_body', json_comment)
        artifact_comment_add(request)
        eq_(af.comments[0].comment, 'test')
        eq_(len(af.root_comments), 1)
        if reply:
            json_comment['parent_id'] = af.comments[0].id
            json_comment['comment'] = 'test2'
            artifact_comment_add(request)
            DBSession.refresh(af)  # Or initial data is cached
            eq_(af.comments[1].comment, 'test2')
            eq_(len(af.root_comments), 1)

        mailer = get_mailer(request)
        eq_(mail_count, len(mailer.queue))

        return af

    def test_edit_comment(self):
        af = self.add_comment(reply=False)
        comment = af.comments[0]
        assert_false(comment.edited)
        request = self.generic_request(user=self.user2)
        request.matchdict['id'] = comment.id
        artifact_comment_edit(request)
        eq_(request.response.status_code, HTTPForbidden.code)
        request.user = self.user
        artifact_comment_edit(request)
        eq_(request.response.status_code, HTTPBadRequest.code)
        request.POST['value'] = 'test_edited'
        eq_({'OK': 'OK'}, artifact_comment_edit(request))
        assert_true(comment.edited)
        eq_(comment.comment, "test_edited")

    def test_delete_comment(self):
        af = self.add_comment(reply=False)
        comment = af.comments[0]
        request = self.generic_request(user=self.user2)
        request.matchdict['id'] = comment.id
        assert_raises(HTTPForbidden, artifact_comment_delete, request)
        request.user = self.user
        artifact_comment_delete(request)
        DBSession.refresh(af)
        eq_(0, len(af.comments))

    def test_add_comment_mails(self):
        # Adding two comments as different users - this should trigger an email
        af = self.add_comment(reply=False)
        self.add_comment(reply=False, mail_count=1, user=self.user2, parent_id=af.comments[0].id, af=af)

    def test_add_comment_artifact_cascade(self):
        af = self.add_comment()
        # And make sure the comment is deleted when the artifact is
        DBSession.delete(af)
        eq_([], DBSession.query(Comment).all())

    def test_add_comment_user_cascade(self):
        af = self.add_comment()
        # And make sure the comment is deleted when the artifact is
        DBSession.delete(af.comments[0].user)
        eq_([], DBSession.query(Comment).all())

    def test_add_comment_parent_cascade(self):
        self.add_comment()
        # And make sure the comment is deleted when the parent comment is
        # noinspection PyComparisonWithNone
        parent = DBSession.query(Comment).filter(Comment.replies != None).one()
        DBSession.delete(parent)
        eq_([], DBSession.query(Comment).all())

    def add_delivery(self):
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
        return af, delivery

    def test_add_delivery(self):
        af, delivery = self.add_delivery()
        # And delete it
        request = self.generic_request()
        request.matchdict['id'] = delivery.id
        eq_(200, artifact_delivery_delete(request).status_code)
        DBSession.refresh(af)
        eq_(0, len(af.deliveries))

    def test_add_delivery_artifakt_cascade(self):
        af, delivery = self.add_delivery()
        # Delete the artifact and make sure the delivery is deleted too
        DBSession.delete(af)
        eq_([], DBSession.query(Delivery).all())

    def test_add_delivery_customer_cascade(self):
        af, delivery = self.add_delivery()
        # Delete the customer and make sure the delivery is deleted too
        DBSession.delete(delivery.to)
        eq_([], DBSession.query(Delivery).all())

    def test_add_delivery_user_cascade(self):
        af, delivery = self.add_delivery()
        # Delete the user and make sure the delivery is deleted too
        DBSession.delete(delivery.by)
        eq_([], DBSession.query(Delivery).all())
        # Deleting the user would nuke the artifact too
        eq_([], DBSession.query(Artifakt).all())

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

    def test_artifact_search(self):
        af = self.simple_upload()
        req = self.generic_request()

        def with_search(sstr, should_find):
            req.matchdict['string'] = sstr
            data = search(req)
            eq_(1 if should_find else 0, data['artifacts'].count())
            if should_find:
                af_res = data['artifacts'][0]
                eq_(af.filename, af_res.filename)
                eq_(af.sha1, af_res.sha1)

        with_search(af.filename, should_find=True)
        with_search(af.filename + "U", should_find=False)

    def test_artifacts(self):
        af = self.simple_upload()
        data = artifacts(self.generic_request())
        eq_(1, data['artifacts'].count())
        af_res = data['artifacts'][0]
        eq_(af.filename, af_res.filename)
        eq_(af.sha1, af_res.sha1)

    def test_artifacts_all(self):
        af = self.simple_upload()
        req = self.generic_request()
        req.GET["limit"] = 0
        data = artifacts(req)
        eq_(1, data['artifacts'].count())
        af_res = data['artifacts'][0]
        eq_(af.filename, af_res.filename)
        eq_(af.sha1, af_res.sha1)

    def test_artifacts_json(self):
        af = self.simple_upload()
        data = artifacts_json(self.generic_request())
        eq_(1, len(data['artifacts']))
        af_json = data['artifacts'][0]
        eq_(af.filename, af_json['filename'])
        eq_(af.sha1, af_json['sha1'])

    def test_artifact_json(self):
        af = self.simple_upload()
        request = self.generic_request()
        request.matchdict['sha1'] = af.sha1
        data = artifact_json(request)
        eq_(af.filename, data['filename'])
        eq_(af.sha1, data['sha1'])

        # def test_password_reset(self):
        #
        #     request = self.generic_request()
        #     # Mock request.registry['config'].fullauth
        #     o = type('', (), {})()
        #     o.fullauth = ''
        #     request.registry['config'] = o
        #     # Mock localization
        #     request._ = dummy_autotranslate
        #     # Request must have an email
        #     request.POST['email'] = request.user.email
        #
        #     prv = PasswordResetView(request)
        #     eq_(1, prv.post())


class TestAdmin(BaseTest):
    # TODO: Use something like pyramid.paster.get_app('testing.ini') to test the permissions
    def test_admin(self):
        request = self.generic_request()
        data = admin(request)
        eq_(200, request.response.status_code)
        assert_in('data', data)
        assert_in('Data storage', data['data'])
        assert_true(os.path.isdir(data['data']['Data storage']))

    def test_verify_fs(self):
        # TODO: Should also test with some items in the lists
        request = self.generic_request()
        request.registry.settings['mail.queue_path'] = 'maildir'
        data = verify_fs(request)
        eq_(200, request.response.status_code)
        assert_in('not_on_disk', data)
        assert_in('not_in_db', data)
        eq_(0, len(data['not_in_db']))
        eq_(0, len(data['not_on_disk']))


class TestTime(unittest.TestCase):
    def test_zero(self):
        eq_(duration_string(0), '0 seconds')
