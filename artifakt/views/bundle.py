from pyramid.view import view_config

from artifakt import DBSession
from artifakt.models.models import Artifakt


@view_config(route_name='bundle', renderer='artifakt:templates/bundle.jinja2')
def bundle(request):
    return {'bundle': DBSession.query(Artifakt).filter(Artifakt.sha1 == request.matchdict["sha1"])
                                               .filter(Artifakt.filename == None).one()}
