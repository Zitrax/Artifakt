from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import Response
from pyramid.view import view_config
from sqlalchemy.orm.exc import NoResultFound

from artifakt import DBSession
from artifakt.models.models import Artifakt


@view_config(route_name='artifacts', renderer='artifakt:templates/artifacts.jinja2')
def artifacts(_):
    return {'artifacts': DBSession.query(Artifakt).all()}


@view_config(route_name='artifacts_json', renderer='json')
def artifacts_json(_):
    return {'artifacts': [a.to_dict() for a in DBSession.query(Artifakt).all()]}


def get_artifact(request):
    sha1 = request.matchdict["sha1"]
    try:
        return DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
    except(NoResultFound):
        raise HTTPNotFound("No artifact with sha1 {} found".format(sha1))


@view_config(route_name='artifact', renderer='artifakt:templates/artifact.jinja2')
def artifact(request):
    return {'artifact': get_artifact(request)}


@view_config(route_name='artifact_json', renderer='json')
def artifact_json(request):
    return get_artifact(request).to_dict()


@view_config(route_name='artifact_delete')
def artifact_json(request):
    af = get_artifact(request)
    DBSession.delete(af)
    return Response(status_int=302, location="/artifacts")
