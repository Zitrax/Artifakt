import hashlib
import json
import os
import shutil
from tempfile import NamedTemporaryFile

from pyramid.view import view_config

from artifakt.models.models import Artifakt, DBSession, Repository, Vcs


def validate_metadata(data):
    if not data:
        return data

    def validate(name, values):
        if name in data:
            diff = set(data[name].keys()).difference(values)
            if diff:
                raise ValueError("Metadata for {} contains unknown/invalid values: {}".format(name, str(diff)))

    # FIXME; What to validate can be taken from the metadata_keys
    validate("artifakt", {'comment'})
    validate("repository", {'url', 'name'})
    validate("vcs", {'revision'})

    return data


# FIXME: Move
def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.flush()
        return instance


@view_config(route_name='upload', renderer='json', request_method='POST')
def upload_post(request):
    # TODO: Handle known exceptions better instead of default 500
    # TODO: Allow multiple files ? ( it gets complicated with http status )
    # TODO: Check performance and memory usage. Might need to read and write in chunks
    # TODO: Use a transaction to rollback everything if something failed
    artifacts = []

    if "file" not in request.POST:
        request.response.status = 400
        return {'error': 'Missing file field in POST request'}

    metadata = json.loads(request.POST.getone('metadata')) if 'metadata' in request.POST else None
    validate_metadata(metadata)
    print(request.POST)
    for item in request.POST.getall('file'):
        tmp = NamedTemporaryFile(delete=False, prefix='artifakt_')
        try:
            sha1_hash = hashlib.sha1()
            print(item)
            content = item.file.read()
            tmp.write(content)
            sha1_hash.update(content)
            sha1 = sha1_hash.hexdigest()

            if DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).count() > 0:
                request.response.status = 409  # Conflict
                return {'error': "Artifact with sha1 {} already exists".format(sha1)}

            storage = request.registry.settings['artifakt.storage']

            _dir = os.path.join(storage, sha1[0:2])
            if not os.path.exists(_dir):
                os.makedirs(_dir)

            blob = os.path.join(_dir, sha1[2:])

            if os.path.exists(blob):
                request.response.status = 409  # Conflict
                return {'error': "File with sha1 {} already exists".format(sha1)}

            shutil.move(tmp.name, blob)

            repo = None
            if 'repository' in metadata:
                repo = get_or_create(DBSession, Repository, url = metadata['repository']['url'])
            vcs = None
            if repo and 'vcs' in metadata:
                vcs = get_or_create(DBSession, Vcs, repository=repo, revision=metadata['vcs']['revision'])

            ameta = metadata['artifakt'] if 'artifakt' in metadata else {}

            # noinspection PyArgumentList
            af = Artifakt(filename=item.filename, sha1=sha1, vcs=vcs, **ameta)
            artifacts.append(af)
            DBSession.add(af)

        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    return {"artifacts": [a.sha1 for a in artifacts]}


@view_config(route_name='upload', renderer='artifakt:templates/upload_form.jinja2', request_method="GET")
def upload_form(_):
    return {"metadata": Artifakt.metadata_keys()}
