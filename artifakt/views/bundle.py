from pyramid.httpexceptions import HTTPNotFound
from pyramid.view import view_config

from artifakt import DBSession
from artifakt.models.models import Artifakt


@view_config(route_name='bundle', renderer='artifakt:templates/bundle.jinja2')
def bundle(request):
    sha1 = request.matchdict["sha1"]
    bundle_ = DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one_or_none()
    if bundle_:
        return {'bundle': bundle_}
    raise HTTPNotFound("No bundle with sha1 {} found".format(sha1))
