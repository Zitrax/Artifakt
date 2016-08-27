from pyramid.view import view_config
from sqlalchemy import or_

from artifakt import DBSession
from artifakt.models.models import Artifakt, Comment


@view_config(route_name='home', renderer='artifakt:templates/home.jinja2')
def artifact(_):
    return {'artifacts': DBSession.query(Artifakt)
                                  .filter(or_(Artifakt.is_bundle, Artifakt.bundle_id == None))
                                  .order_by(Artifakt.created.desc()).limit(5),
            'comments': DBSession.query(Comment).filter(~Comment.deleted).order_by(Comment.time.desc()).limit(5)}
