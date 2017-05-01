from pyramid.view import view_config
from pyramid_fullauth.models import User

from artifakt import DBSession


@view_config(route_name='users', renderer='artifakt:templates/users.jinja2')
def users(_):
    return {'users': DBSession.query(User).all()}
