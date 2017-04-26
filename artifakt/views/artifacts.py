import mimetypes
import os
import re
import tarfile
import zipfile
from datetime import datetime

from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPConflict, HTTPFound, HTTPForbidden, HTTPException
from pyramid.response import Response, FileResponse
from pyramid.view import view_config
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Message
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from artifakt import DBSession
from artifakt.models.models import Artifakt, schemas, Delivery, Comment


@view_config(route_name='artifacts', renderer='artifakt:templates/artifacts.jinja2')
def artifacts(request):
    sort_field = request.GET.get('sort', 'created')
    sort_on = getattr(Artifakt, sort_field, Artifakt.created)
    asc = 'asc' in request.GET
    return artifact_list(request,
                         DBSession.query(Artifakt).order_by(sort_on if asc else sort_on.desc()),
                         asc)


def artifact_list(request, query, asc=False):
    count = query.count()
    offset = int(request.GET.get("offset", 0))
    limit = int(request.GET.get("limit", 20))
    page = (offset // limit + 1) if limit else 1
    page_count = (count // limit) if limit else 1
    if limit * page_count < count:
        page_count += 1
    res = {"limit": limit, "page": page, "page_count": page_count,
           'asc': asc,
           'pages': sorted({1,
                            page - 1 if page > 1 else 1,
                            page,
                            page + 1 if page < page_count else page_count,
                            page_count})}
    if limit:
        res['artifacts'] = query.offset(offset).limit(limit)
    else:
        res['artifacts'] = query
    return res


@view_config(route_name='artifacts_json', renderer='json')
def artifacts_json(_):
    return {'artifacts': [schemas['artifakt'].dump(a).data for a in DBSession.query(Artifakt).all()]}


def get_artifact(request):
    if "sha1" not in request.matchdict:
        raise HTTPBadRequest("Missing sha1 argument")
    sha1 = request.matchdict["sha1"]
    try:
        if len(sha1) == 40:
            return DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
        else:
            return DBSession.query(Artifakt).filter(Artifakt.sha1.like(sha1 + '%')).one()
    except MultipleResultsFound:
        raise HTTPConflict("This abbreviated sha1 matches multiple artifacts")
    except NoResultFound:
        raise HTTPNotFound("No artifact with sha1 {} found".format(sha1))


@view_config(route_name='artifact_edit', renderer='json', request_method="POST")
def artifact_edit(request):
    # For the exceptions we are forcing txt/json responses
    # But apparently it should work by default if x-editable
    # had added json in it's accept header - I could not find
    # that it was configurable though.
    if "name" not in request.POST:
        request.response.status = HTTPBadRequest.code
        return 'ERROR: Missing name in request'
    name = request.POST['name']
    if name not in ['name']:  # Supported attributes to edit
        request.response.status = HTTPBadRequest.code
        return 'ERROR: Attribute ' + name + ' is not editable'
    if "value" not in request.POST:
        request.response.status = HTTPBadRequest.code
        return 'ERROR: Missing value in request'
    value = request.POST['value']

    try:
        af = get_artifact(request)
        old_name = af.name
        setattr(af, name, value)

        # Add a comment describing the change
        comment = Comment()
        comment.artifakt_sha1 = request.matchdict['sha1']
        comment.comment = "Changed name from '{}' to '{}'".format(old_name, value)
        comment.user_id = request.user.id
        DBSession.add(comment)
        DBSession.flush()
        notify_new_comment(request, comment)

    except HTTPException as ex:
        request.response.status = ex.status_code
        return ex.message

    return {'OK': 'OK'}


@view_config(route_name='artifact', renderer='artifakt:templates/artifact.jinja2')
def artifact(request):
    af = get_artifact(request)
    if len(request.matchdict['sha1']) != 40:
        raise HTTPFound(location='/artifact/' + af.sha1)
    return {'artifact': af}


@view_config(route_name='artifact_json', renderer='json')
def artifact_json(request):
    return schemas['artifakt'].dump(get_artifact(request)).data


# @view_config(route_name='artifact_edit', request_method='POST')
# def artifact_edit(request):
#     af = get_artifact(request)
#     for attr in request.metadata:
#         print(attr)


@view_config(route_name='artifact_delete')
def artifact_delete(request):
    af = get_artifact(request)
    if not af.is_bundle:
        if af.bundles:
            raise HTTPForbidden("This artifact can not be deleted. It belongs to a bundle.")

    if request.user.id != af.uploaded_by:
        raise HTTPForbidden("Not your artifact")

    DBSession.delete(af)

    return Response(status_int=302, location="/artifacts")


@view_config(route_name='artifact_download')
def artifact_attachment_view(request):
    return artifact_download(request, inline=False)


@view_config(route_name='artifact_view_raw')
def artifact_inline_view_raw(request):
    return artifact_download(request, inline=True)


def artifact_download(request, inline):
    af = get_artifact(request)

    if af.is_bundle:
        if inline:
            raise HTTPBadRequest("Inline view not supported for bundles")
        # We have a bundle. So we need to prepare a zip (unless we already have one)
        # TODO: Need to handle multiple incoming requests (locking)
        disk_name = af.file
        if not os.path.exists(disk_name):
            with zipfile.ZipFile(disk_name, 'w', compression=zipfile.ZIP_BZIP2) as _zip:
                for cf in af.artifacts:
                    _zip.write(cf.file, arcname=cf.bundle_filename(af))
        file_name = af.name + ".zip"
    else:
        disk_name = af.file
        file_name = af.filename

    mime, encoding = mimetypes.guess_type(file_name)
    if mime is None:
        mime = ('text/plain' if inline else 'application/octet-stream')
    # If the current simple approach proves to be a problem the discussion
    # at http://stackoverflow.com/q/93551/11722 can be considered.
    response = FileResponse(disk_name, request=request, content_type=mime)
    response.content_disposition = '{}; filename="{}"'.format('inline' if inline else 'attachment', file_name)
    # Specifically needed for jquery.fileDownload
    response.set_cookie('fileDownload', 'true')
    return response


@view_config(route_name='artifact_view', renderer="artifakt:templates/artifact_highlight.jinja2")
def artifact_inline_view(request):
    af = get_artifact(request)
    return {'content': af.file_content}


@view_config(route_name='artifact_view_archive', renderer="artifakt:templates/artifact_archive.jinja2")
def artifact_archive_view(request):
    af = get_artifact(request)
    mime = af.mime
    ret = {'title': 'Artifact archive: ' + af.filename}
    if mime == 'application/x-tar':
        with tarfile.open(af.file) as tar:
            ret['tarfiles'] = tar.getmembers()
            return ret
    if mime in ['application/zip', 'application/x-zip-compressed']:
        with zipfile.ZipFile(af.file) as _zip:
            ret['zipfiles'] = _zip.infolist()
            return ret
    return {"error": "Mimetype {} is not a known/supported archive".format(mime)}


@view_config(route_name='artifact_comment_add', request_method="POST", renderer="json")
def artifact_comment_add(request):
    data = request.json_body
    data['user_id'] = request.user.id
    comment = schemas['comment'].make_instance(data)
    DBSession.add(comment)
    DBSession.flush()
    notify_new_comment(request, comment)
    return schemas['comment'].dump(comment).data


def notify_new_comment(request, comment):
    # Find all parents excluding commenter
    # Include the uploader of the artifact
    parents = {p.user for p in comment.parents}.union({comment.artifakt.uploader})
    parents = set(filter(lambda u: u != comment.user, parents))
    if parents:
        mailer = get_mailer(request)
        artifact_url = re.search(r'^(.*artifact/[0-9a-f]{6}).*', request.url).group(1)
        message = Message(subject="[Artifakt] New comment",
                          recipients=[p.email for p in parents],
                          body="A new comment was added to: {}\n\n{}\n\nBy {}".format(artifact_url, comment.comment,
                                                                                      comment.user.username))
        mailer.send_to_queue(message)


@view_config(route_name='artifact_comment_delete', request_method="POST")
def artifact_comment_delete(request):
    comment = DBSession.query(Comment).filter(Comment.id == request.matchdict['id']).one()
    if request.user.id != comment.user_id:
        raise HTTPForbidden("Not your comment")
    comment.delete()
    return Response()


@view_config(route_name='artifact_comment_edit', renderer='json', request_method="POST")
def artifact_comment_edit(request):
    comment = DBSession.query(Comment).filter(Comment.id == request.matchdict['id']).one()
    if request.user.id != comment.user_id:
        request.response.status = HTTPForbidden.code
        return "ERROR: Not your comment"
    if "value" not in request.POST:
        request.response.status = HTTPBadRequest.code
        return 'ERROR: Missing value in request'
    value = request.POST['value']
    comment.comment = value
    comment.edited = True
    return {'OK': 'OK'}


@view_config(route_name='artifact_delivery_add', request_method="POST", renderer="json")
def artifact_delivery_add(request):
    data = request.json_body
    data['time'] = datetime.strptime(data['time'], '%Y-%m-%d')
    data['user_id'] = request.user.id
    delivery = schemas['delivery'].make_instance(data)
    DBSession.add(delivery)
    DBSession.flush()
    return schemas['delivery'].dump(delivery).data


@view_config(route_name='artifact_delivery_delete', request_method="POST")
def artifact_delivery_delete(request):
    delivery = DBSession.query(Delivery).filter(Delivery.id == request.matchdict['id']).one()
    DBSession.delete(delivery)
    return Response()
