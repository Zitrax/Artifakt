from artifakt import DBSession
from artifakt.models.models import Customer
from pyramid.view import view_config


@view_config(route_name='customers', renderer='artifakt:templates/customers.jinja2')
def artifacts(_):
    return {'customers': DBSession.query(Customer).order_by(Customer.name.desc()).all()}
