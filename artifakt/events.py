from pyramid.events import subscriber
from pyramid.httpexceptions import HTTPFound, HTTPSeeOther
from pyramid_fullauth.events import AfterRegister, AfterResetRequest, AfterReset
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message


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


@subscriber(AfterResetRequest)
def after_reset_request(event):
    """Send out a password reset email"""
    mailer = get_mailer(event.request)
    message = Message(subject="[Artifakt] Password reset",
                      recipients=event.user.email,
                      body="To reset your artifakt account password follow this link: {}/password/reset/{}".format(
                          event.request.application_url, event.user.reset_key))
    mailer.send_to_queue(message)


@subscriber(AfterReset)
def after_reset(_):
    """Redirect to login after password reset"""
    raise HTTPSeeOther(location='/')
