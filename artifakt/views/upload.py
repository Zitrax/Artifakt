import hashlib
import os
import shutil
from tempfile import NamedTemporaryFile

from pyramid.view import view_config

from artifakt.models.models import Artifakt, DBSession


@view_config(route_name='upload_post', renderer='json', request_method='POST')
def upload_post(request):
    # TODO: Add metadata
    # TODO: Allow multiple files ? ( it gets complicated with http status )
    # TODO: Check performance and memory usage. Might need to read and write in chunks
    artifacts = []
    for item in request.POST.values():
        tmp = NamedTemporaryFile(delete=False, prefix='artifakt_')
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

            shutil.move(tmp.name, blob)

            # noinspection PyArgumentList
            af = Artifakt(filename=item.filename, sha1=sha1)
            artifacts.append(af)
            DBSession.add(af)

        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    return {"artifacts": [a.sha1 for a in artifacts]}
