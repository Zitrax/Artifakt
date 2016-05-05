from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from artifakt.models.models import (
    DBSession,
    Base,
    )


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    config = Configurator(settings=settings)
    config.include('pyramid_jinja2')
    config.include('pyramid_chameleon')
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('home', '/')
    config.add_route('artifact', '/artifact/{sha1}')
    config.add_route('artifacts', '/artifacts')
    config.add_route('artifacts_json', '/artifacts.json')
    config.add_route('upload_post', '/upload')
    config.scan()
    return config.make_wsgi_app()
