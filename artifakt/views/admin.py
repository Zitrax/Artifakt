from os.path import abspath

from pyramid.view import view_config

from artifakt.models.models import storage


@view_config(route_name='admin', renderer='artifakt:templates/admin.jinja2')
def admin(_):
    return {'data': {
        'Data storage': abspath(storage)}
    }
