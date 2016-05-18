import hashlib
import json
import os
import shutil
from tempfile import NamedTemporaryFile

from pyramid.view import view_config

from artifakt.models.models import Artifakt, DBSession, schemas


def validate_metadata(data):
    if not data:
        return data

    ret = {}
    for key in data.keys():
        if key in data:
            if any(v != '' for v in data[key].values()):
                ret[key] = schemas[key].make_instance(data[key])

    return ret


@view_config(route_name='upload', renderer='json', request_method='POST')
def upload_post(request):
    # TODO: Handle known exceptions better instead of default 500
    # TODO: Allow multiple files ? ( it gets complicated with http status )
    # TODO: Check performance and memory usage. Might need to read and write in chunks
    artifacts = []

    for field in ['file', 'metadata']:
        if field not in request.POST:
            request.response.status = 400
            return {'error': 'Missing {} field in POST request'.format(field)}

    metadata = json.loads(request.POST.getone('metadata')) if 'metadata' in request.POST else None
    for item in request.POST.getall('file'):
        tmp = NamedTemporaryFile(delete=False, prefix='artifakt_')
        blob = None
        try:
            sha1_hash = hashlib.sha1()
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

            # Must use copy instead of move due to Windows file-in-use issues
            shutil.copy(tmp.name, blob)

            # Update metadata with needed additional data
            if 'artifakt' not in metadata:
                metadata['artifakt'] = {}
            metadata['artifakt']['filename'] = item.filename
            metadata['artifakt']['sha1'] = sha1

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

            DBSession.add(af)
            artifacts.append(af)
            DBSession.flush()
        except Exception:
            if os.path.exists(blob):
                os.remove(blob)
            raise
        finally:
            tmp.close()
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    return {"artifacts": [a.sha1 for a in artifacts]}


@view_config(route_name='upload', renderer='artifakt:templates/upload_form.jinja2', request_method="GET")
def upload_form(_):
    return {"metadata": Artifakt.metadata_keys()}
