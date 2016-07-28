from artifakt import DBSession
from artifakt.models.models import Customer, schemas
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.response import Response
from pyramid.view import view_config


@view_config(route_name='customers', renderer='artifakt:templates/customers.jinja2')
def artifacts(_):
    return {'customers': DBSession.query(Customer).order_by(Customer.name.desc()).all()}


@view_config(route_name='customers_json', renderer='json')
def artifacts_json(_):
    return {'customers': [schemas['customer'].dump(c).data for c in DBSession.query(Customer).all()]}


@view_config(route_name='customers', request_method='POST')
def add_customer(request):
    if 'name' not in request.POST:
        raise HTTPBadRequest("Missing parameter 'name'")

    customer = schemas['customer'].make_instance(request.POST)
    print(customer)
    DBSession.add(customer)
    DBSession.flush()
    return Response()

