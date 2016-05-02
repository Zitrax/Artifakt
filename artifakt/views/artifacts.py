from pyramid.view import view_config

from artifakt import DBSession
from artifakt.models.models import Artifakt


@view_config(route_name='artifacts', renderer='artifakt:templates/artifacts.jinja2')
def artifacts(_):
    return {'artifacts': DBSession.query(Artifakt).all()}


@view_config(route_name='artifacts_json', renderer='json')
def artifacts_json(_):
    return {'artifacts': [a.to_dict() for a in DBSession.query(Artifakt).all()]}
