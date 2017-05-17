from pyramid.httpexceptions import HTTPBadRequest
from pyramid.view import view_config
from sqlalchemy import func

from artifakt import DBSession
from artifakt.models.models import Repository, schemas


@view_config(route_name='repositories', renderer='artifakt:templates/repositories.jinja2')
def repositories(_):
    return {'repositories': DBSession.query(Repository).order_by(
        func.lower(Repository.name).asc()).all()}


@view_config(route_name='repositories_json', renderer='json')
def repositories_json(request):
    if "editable" in request.GET:
        res = []
        for rep in DBSession.query(Repository).all():
            res.append({'value': rep.id, 'text': rep.name})
        return res
    else:
        return {'repositories': [schemas['repository'].dump(a).data for a in DBSession.query(Repository).all()]}


@view_config(route_name='repository', renderer='artifakt:templates/repository.jinja2')
def repository(request):
    if "id" not in request.matchdict:
        raise HTTPBadRequest("Missing id argument")
    _id = request.matchdict["id"]
    return {'repository': DBSession.query(Repository).filter(Repository.id == _id).one()}
