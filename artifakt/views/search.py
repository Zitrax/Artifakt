from artifakt import DBSession
from artifakt.models.models import Artifakt
from pyramid.view import view_config
from sqlalchemy import or_


@view_config(route_name='search', renderer='artifakt:templates/artifacts.jinja2')
def search(request):
    search_str = '%' + request.matchdict['string'] + '%'
    return {'artifacts': DBSession.query(Artifakt).filter(
        or_(Artifakt.filename.like(search_str),
            Artifakt.comment.like(search_str))).order_by(Artifakt.created.desc()).all()}
