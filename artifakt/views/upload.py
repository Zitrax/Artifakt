import hashlib
import json
import os
import shutil

from artifakt.models.models import Artifakt, DBSession, schemas, Repository
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.view import view_config


def validate_metadata(data):
    if not data:
        return data

    ret = {}
    for key in data.keys():
        if key in data:
            if any(v != '' for v in data[key].values()):
                ret[key] = schemas[key].make_instance(data[key])

    return ret


def _upload_post(request, artifacts):
    for field in ['file', 'metadata']:
        if field not in request.POST:
            request.response.status = 400
            return {'error': 'Missing {} field in POST request'.format(field)}

    metadata = json.loads(request.POST.getone('metadata')) if 'metadata' in request.POST else None
    files = request.POST.getall('file')

    if len(files) == 0 or (len(files) == 1 and not hasattr(files[0], 'file')):
        raise HTTPBadRequest("No files or invalid file")

    # Don't know the full sha1 until later - so start out with 0
    if len(files) > 1:
        try:
            fn = metadata['artifakt']['comment']
        except KeyError:
            fn = None
        bundle = Artifakt(sha1='0' * 40,
                          is_bundle=True,
                          filename=fn,
                          uploaded_by=request.user.id)
        # For bundles we are using the comment for the bundle name - so drop it on the files
        try:
            metadata['artifakt']['comment'] = None
        except KeyError:
            pass
    else:
        bundle = None

    for item in files:
        blob = None
        try:
            sha1_hash = hashlib.sha1()
            content = item.file.read()
            sha1_hash.update(content)
            sha1 = sha1_hash.hexdigest()

            existing = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one_or_none()
            if existing is not None:
                # This is fine if part of a bundle - in that case we can just continue
                if bundle:
                    pass
                # If not part of a bundle - we should make sure to flag as keep_alive
                else:
                    request.response.status = 302  # Since metadata will not be used we need to tell user
                    existing.keep_alive = True

                artifacts.append(existing)
                continue

            storage = request.registry.settings['artifakt.storage']

            _dir = os.path.join(storage, sha1[0:2])
            if not os.path.exists(_dir):
                os.makedirs(_dir)

            blob = os.path.join(_dir, sha1[2:])

            if os.path.exists(blob):
                request.response.status = 409  # Conflict
                return {'error': "File {} with sha1 {} already exists".format(os.path.basename(blob), sha1)}

            item.file.seek(0)
            with open(blob, 'wb') as blob_file:
                shutil.copyfileobj(item.file, blob_file)

            # Update metadata with needed additional data
            if 'artifakt' not in metadata:
                metadata['artifakt'] = {}
            metadata['artifakt']['filename'] = item.filename
            metadata['artifakt']['sha1'] = sha1
            metadata['artifakt']['uploader'] = request.user
            metadata['artifakt']['keep_alive'] = bundle is None

            prepare_repo(metadata)
            # Will validate and create objects
            objects = validate_metadata(metadata)

            af = objects['artifakt']

            repo = None
            if 'repository' in objects:
                repo = objects['repository']
            if repo and 'vcs' in objects:
                vcs = objects['vcs']
                vcs.repository = repo
                af.vcs = vcs

            artifacts.append(af)
            DBSession.flush()
        except Exception:
            if blob is not None and os.path.exists(blob):
                os.remove(blob)
            raise

    # Calculate bundle sha1
    if bundle:
        bundle.sha1 = '{:040x}'.format(sum(int(a.sha1, 16) for a in artifacts) % int('f' * 40, 16))
        for a in artifacts:
            a.bundles.append(bundle)
        DBSession.flush()

    return {"artifacts": [a.sha1 for a in artifacts]}


def prepare_repo(metadata):
    """Workaround for repos. Validation uses the primary key - but repos have a unique
    url so we need to find the primary key if we already have this url to reuse it."""
    if 'repository' in metadata:
        repo = DBSession.query(Repository).filter(Repository.url == metadata['repository']['url']).one_or_none()
        if repo is not None:
            metadata['repository']['id'] = repo.id


@view_config(route_name='upload', renderer='json', request_method='POST')
def upload_post(request):
    # TODO: Handle known exceptions better instead of default 500
    # TODO: Allow multiple files ? ( it gets complicated with http status )
    # TODO: Check performance and memory usage. Might need to read and write in chunks
    artifacts = []

    def cleanup(exc):
        """If a bundle was partially uploaded - delete the remains"""
        if exc:
            for af in artifacts:
                if os.path.exists(af.file):
                    os.remove(af.file)
        elif request.response.status_int not in (200, 302) and len(artifacts):
            for af in artifacts:
                DBSession.delete(af)
            DBSession.flush()

    try:
        res = _upload_post(request, artifacts)
        if request.response.status_int != 200:
            cleanup(False)
        return res
    except Exception:
        cleanup(True)
        raise


@view_config(route_name='upload', renderer='artifakt:templates/upload_form.jinja2', request_method="GET")
def upload_form(_):
    return {"metadata": Artifakt.metadata_keys()}
