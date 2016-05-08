from pyramid.view import view_config


@view_config(route_name='home', renderer='artifakt:templates/home.jinja2')
def artifact(request):
    return {}
