from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound
from pyramid.view import view_config
from pyramid_fullauth.models import User
from sqlalchemy import func

from artifakt import DBSession


@view_config(route_name='users', renderer='artifakt:templates/users.jinja2')
def users(_):
    return {'users': DBSession.query(User).order_by(func.lower(User.username)).all()}


@view_config(route_name='user', renderer='artifakt:templates/user.jinja2')
def user(request):
    if "id" not in request.matchdict:
        raise HTTPBadRequest("Missing id argument")
    id = request.matchdict['id']
    user = DBSession.query(User).filter(User.id == id).one_or_none()
    if user is None:
        raise HTTPNotFound("No user with id " + str(id))
    return {'user': user}
