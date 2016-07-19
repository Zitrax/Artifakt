from pyramid.events import subscriber
from pyramid.httpexceptions import HTTPFound
from pyramid_fullauth.events import AfterRegister


@subscriber(AfterRegister)
def after_register(event):
    """Redirect to login page after a successful registering"""
    if event.response_values['status']:

        # The standard register view only sets some values
        # we want a few more
        post = event.request.POST
        for data in ['firstname', 'lastname', 'username']:
            if data in post:
                setattr(event.user, data, post[data])

        raise HTTPFound(location='/login')

