from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response
from pyramid.view import view_config
from sqlalchemy import func

from artifakt import DBSession
from artifakt.models.models import Customer, schemas


@view_config(route_name='customer', renderer='artifakt:templates/customer.jinja2')
def customer(request):
    if "id" not in request.matchdict:
        raise HTTPBadRequest("Missing id argument")
    _id = request.matchdict["id"]
    return {'customer': DBSession.query(Customer).filter(Customer.id == _id).one()}


@view_config(route_name='customers', renderer='artifakt:templates/customers.jinja2')
def customers(_):
    return {'customers': DBSession.query(Customer).order_by(
        func.lower(Customer.name).asc()).all()}


@view_config(route_name='customers_json', renderer='json')
def customers_json(_):
    return {'customers': [schemas['customer'].dump(c).data for c in DBSession.query(Customer).all()]}


@view_config(route_name='customers', request_method='POST')
def add_customer(request):
    if 'name' not in request.POST:
        raise HTTPBadRequest("Missing parameter 'name'")

    new_customer = schemas['customer'].make_instance(request.POST)
    DBSession.add(new_customer)
    DBSession.flush()
    return Response()
