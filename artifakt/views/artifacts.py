from pyramid.view import view_config

from artifakt import DBSession
from artifakt.models.models import Artifakt


@view_config(route_name='artifacts', renderer='artifakt:templates/artifacts.jinja2')
def my_view(request):
    return {'artifacts': DBSession.query(Artifakt).all()}

