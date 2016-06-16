from pyramid.view import view_config

from artifakt import DBSession
from artifakt.models.models import Bundle


@view_config(route_name='bundle', renderer='artifakt:templates/bundle.jinja2')
def bundle(request):
    return {'bundle': DBSession.query(Bundle).filter(Bundle.id == request.matchdict["id"]).one()}
