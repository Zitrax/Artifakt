from pyramid.events import subscriber
from pyramid.httpexceptions import HTTPFound
from pyramid_fullauth.events import AfterRegister


@subscriber(AfterRegister)
def after_register(event):
    """Redirect to login page after a successful registering"""
    if event.response_values['status']:
        raise HTTPFound(location='/login')
