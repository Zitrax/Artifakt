import logging
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from pyramid.config import Configurator
from pyramid.interfaces import IRootFactory
from pyramid.security import Allow, Everyone, ALL_PERMISSIONS
from pyramid_fullauth.auth import BaseACLRootFactoryMixin
from sqlalchemy import engine_from_config
from zope.interface import implementer

from artifakt.models import models
from artifakt.models.models import (
    DBSession,
    Base,
    storage)
from artifakt.utils.time import duration_string

logger = logging.getLogger(__name__)


def include_fullauth(config):
    """Need some patching to use jinja2 templates with fullauth"""

    import tzf.pyramid_yml
    config.include('tzf.pyramid_yml')  # To be able to configure
    config.include('pyramid_basemodel')

    def patched_includeme(orig_includeme):
        def new_include(configurator):
            # Need to force fullauth to treat mako templates as jinja
            # or the asset override will still think we are using mako
            configurator.add_jinja2_renderer('.mako')
            # Important - since fullauth uses a registered factory if set.
            #  set_root_factory(...) can not be used.
            configurator.registry.registerUtility(ArtifaktRootFactory, IRootFactory)
            orig_includeme(configurator)
        return new_include

    import pyramid_fullauth
    pyramid_fullauth.includeme = patched_includeme(pyramid_fullauth.includeme)
    config.include('pyramid_fullauth')

    for view in ['login', 'register', '403', 'reset', 'reset.proceed']:
        config.override_asset(
            to_override='pyramid_fullauth:resources/templates/{}.mako'.format(view),
            override_with='artifakt:templates/{}.jinja2'.format(view))

    config.override_asset(
        to_override='pyramid_fullauth:resources/templates/',
        override_with='artifakt:templates/')


@implementer(IRootFactory)
class ArtifaktRootFactory(BaseACLRootFactoryMixin):
    """Custom factory with acl changes

    The default fullauth mixin hardcodes the user permissions. Instead change that
    to a generic 'user' permission that can be used all over.
    """

    __acl__ = [(Allow, Everyone, 'view'),
               (Allow, 's:superadmin', ALL_PERMISSIONS),
               (Allow, 's:user', 'user'),
               (Allow, 's:inactive', 'user')  # For now - do not care about activation
               ]


def clean_bundle_cache():
    """Clean away cached bundle zip files after 4 hours"""
    cache_dir = os.path.join(storage(), 'zip')
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            abs_f = os.path.join(cache_dir, f)
            age = time.time() - os.stat(abs_f).st_atime
            logger.debug(f + " : " + duration_string(age))
            if age > 14400:  # 4 hours in seconds. TODO: Make it configurable
                logger.info(f + " : DELETED")
                os.remove(abs_f)


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    # FIXME: This is a default unsecure factory
    # my_session_factory = SignedCookieSessionFactory('itsaseekreet')
    config = Configurator(settings=settings)
    config.set_default_permission('user')
    config.include('pyramid_jinja2')
    config.include('pyramid_chameleon')
    include_fullauth(config)

    models.set_storage(settings['artifakt.storage'])
    zip_dir = os.path.join(models.storage(), 'zip')
    if not os.path.exists(zip_dir):
        os.mkdir(zip_dir)

    config.add_static_view('js', 'static/js', cache_max_age=3600)
    config.add_static_view('css', 'static/css', cache_max_age=3600)
    config.add_static_view('img', 'static/img', cache_max_age=3600)
    # This is the jquery ui images
    config.add_static_view('images', 'static/css/images', cache_max_age=3600)
    config.add_static_view('bootstrap', 'static/bootstrap', cache_max_age=3600)

    config.add_route('home', '/')

    # Admin routes
    config.add_route('admin', '/admin')
    config.add_route('verify_fs', '/admin/verify_fs')

    config.add_route('artifact_json', '/artifact/{sha1}.json')
    config.add_route('artifact_hex', '/artifact/{sha1}/hex')
    config.add_route('artifact', '/artifact/{sha1}')
    config.add_route('artifact_edit', '/artifact/{sha1}/edit')
    config.add_route('artifact_delete', '/artifact/{sha1}/delete')
    config.add_route('artifact_download', '/artifact/{sha1}/download')
    config.add_route('artifact_view_raw', '/artifact/{sha1}/view_raw')
    config.add_route('artifact_view', '/artifact/{sha1}/view')
    config.add_route('artifact_view_archive', '/artifact/{sha1}/view_archive')
    config.add_route('artifact_comment_add', '/artifact/{sha1}/comment')
    config.add_route('artifact_comment_delete', '/artifact/{sha1}/comment_delete/{id}')
    config.add_route('artifact_comment_edit', '/artifact/{sha1}/comment_edit/{id}')
    config.add_route('artifact_delivery_add', '/artifact/{sha1}/delivery')
    config.add_route('artifact_delivery_delete', '/artifact/{sha1}/delivery_delete/{id}')

    config.add_route('artifacts', '/artifacts')
    config.add_route('artifacts_json', '/artifacts.json')

    config.add_route('bundle', '/bundle/{sha1}')

    config.add_route('customer', '/customer/{id}')
    config.add_route('customers', '/customers')
    config.add_route('customers_json', '/customers.json')

    config.add_route('repositories', '/repositories')
    config.add_route('repositories_json', '/repositories.json')
    config.add_route('repository', '/repository/{id}')

    config.add_route('upload', '/upload')

    config.add_route('search', '/search/{string}')

    config.add_route('users', '/users')
    config.add_route('user', '/user/{id}')

    config.scan()

    # Starting the scheduler that will be used for periodic tasks
    scheduler = BackgroundScheduler()
    scheduler.add_job(clean_bundle_cache, 'interval', minutes=10, name="Clean bundle cache")
    scheduler.start()

    return config.make_wsgi_app()
