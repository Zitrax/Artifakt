import hashlib
import os
import shutil
from tempfile import NamedTemporaryFile

from pyramid.view import view_config


@view_config(route_name='upload_post', renderer='json', request_method='POST')
def upload_post(request):
    # TODO: Add metadata
    # TODO: Allow multiple files ? ( it gets complicated with http status )
    # TODO: Check performance and memory usage. Might need to read and write in chunks
    # TODO: Insert object into database and return proper json
    for item in request.POST:
        tmp = NamedTemporaryFile(delete=False, prefix='artifakt_')
        try:
            sha1_hash = hashlib.sha1()
            content = request.POST[item].file.read()
            tmp.write(content)
            sha1_hash.update(content)
            sha1 = sha1_hash.hexdigest()
            storage = request.registry.settings['artifakt.storage']

            dir = os.path.join(storage, sha1[0:2])
            if not os.path.exists(dir):
                os.makedirs(dir)

            blob = os.path.join(dir, sha1[2:])

            if os.path.exists(blob):
                request.response.status = 409  # Conflict
                return {'error': "File with sha1 {} already exists".format(sha1)}

            shutil.move(tmp.name, blob)
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)

    return { "OK": "OK" }
