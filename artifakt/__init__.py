from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from artifakt.models import models
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
    # FIXME: This is a default unsecure factory
    # my_session_factory = SignedCookieSessionFactory('itsaseekreet')
    config = Configurator(settings=settings)
    config.include('pyramid_jinja2')
    config.include('pyramid_chameleon')

    models.storage = settings['artifakt.storage']

    config.add_static_view('js', 'static/js', cache_max_age=3600)
    config.add_static_view('css', 'static/css', cache_max_age=3600)
    config.add_static_view('img', 'static/img', cache_max_age=3600)
    config.add_static_view('bootstrap', 'static/bootstrap', cache_max_age=3600)

    config.add_route('home', '/')

    # Admin routes
    config.add_route('admin', '/admin')
    config.add_route('verify_fs', '/admin/verify_fs')

    config.add_route('artifact_json', '/artifact/{sha1}.json')
    config.add_route('artifact', '/artifact/{sha1}')
    config.add_route('artifact_delete', '/artifact/{sha1}/delete')
    config.add_route('artifact_download', '/artifact/{sha1}/download')
    config.add_route('artifact_view_raw', '/artifact/{sha1}/view_raw')
    config.add_route('artifact_view', '/artifact/{sha1}/view')
    config.add_route('artifact_view_archive', '/artifact/{sha1}/view_archive')

    config.add_route('artifacts', '/artifacts')
    config.add_route('artifacts_json', '/artifacts.json')

    config.add_route('bundle', '/bundle/{sha1}')

    config.add_route('upload', '/upload')

    config.scan()

    return config.make_wsgi_app()
