from pyramid.httpexceptions import HTTPBadRequest
from pyramid.view import view_config
from sqlalchemy import func

from artifakt import DBSession
from artifakt.models.models import Repository


@view_config(route_name='repositories', renderer='artifakt:templates/repositories.jinja2')
def repositories(_):
    return {'repositories': DBSession.query(Repository).order_by(
        func.lower(Repository.name).asc()).all()}


@view_config(route_name='repository', renderer='artifakt:templates/repository.jinja2')
def repository(request):
    if "id" not in request.matchdict:
        raise HTTPBadRequest("Missing id argument")
    _id = request.matchdict["id"]
    return {'repository': DBSession.query(Repository).filter(Repository.id == _id).one()}
