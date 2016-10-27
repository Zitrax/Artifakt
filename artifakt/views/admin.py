import os
from os.path import abspath

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPInternalServerError
from sqlalchemy import not_

from artifakt.models.models import storage, DBSession, Artifakt


@view_config(route_name='admin', renderer='artifakt:templates/admin.jinja2', permission='admin')
def admin(_):
    if not storage():
        raise HTTPInternalServerError("storage not set")
    return {'data': {
        'Data storage': abspath(storage())}
    }


@view_config(route_name='verify_fs', renderer='artifakt:templates/verify_fs.jinja2', permission='admin')
def verify_fs(request):
    if not storage():
        raise HTTPInternalServerError("storage not set")
    # First check for files in db that are not on disk
    af_not_on_disk = []
    for af in DBSession.query(Artifakt).filter(not_(Artifakt.is_bundle)).order_by(Artifakt.filename):
        if not af.exists:
            af_not_on_disk.append(af)
    # Then check for files on disk that are not in the db
    maildir = os.path.realpath(request.registry.settings["mail.queue_path"])
    mails = []
    zip = []
    af_not_in_db = []
    for root, directories, filenames in os.walk(abspath(storage())):
        for fn in filenames:
            af = DBSession.query(Artifakt).filter(Artifakt.sha1 == root[-2:] + fn).one_or_none()
            if not af:
                if fn.endswith('.zip'):
                    zip.append(os.path.join(root, fn))
                elif root.startswith(maildir):
                    mails.append(os.path.join(root, fn))
                else:
                    af_not_in_db.append(os.path.join(root, fn))
    return {'not_on_disk': af_not_on_disk,
            'not_in_db': af_not_in_db,
            'mails': mails,
            'zip': zip}
