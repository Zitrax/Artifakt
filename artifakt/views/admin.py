import os
from os.path import abspath

from pyramid.view import view_config

from artifakt.models.models import storage, DBSession, Artifakt


@view_config(route_name='admin', renderer='artifakt:templates/admin.jinja2')
def admin(_):
    return {'data': {
        'Data storage': abspath(storage)}
    }


@view_config(route_name='verify_fs', renderer='artifakt:templates/verify_fs.jinja2')
def verify_fs(_):
    # First check for files in db that are not on disk
    af_not_on_disk = []
    for af in DBSession.query(Artifakt).order_by(Artifakt.filename):
        if not af.exists:
            af_not_on_disk.append(af)
    # Then check for files on disk that are not in the db
    af_not_in_db = []
    for root, directories, filenames in os.walk(storage):
        for fn in filenames:
            af = DBSession.query(Artifakt).filter(Artifakt.filename == fn).one_or_none()
            if not af:
                af_not_in_db.append(os.path.join(root, fn))
    return {'not_on_disk': af_not_on_disk,
            'not_in_db': af_not_in_db}
