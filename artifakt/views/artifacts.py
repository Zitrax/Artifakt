import mimetypes
import tarfile
import zipfile
from collections import defaultdict

from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest
from pyramid.response import Response, FileResponse
from pyramid.view import view_config
from sqlalchemy.orm.exc import NoResultFound

from artifakt import DBSession
from artifakt.models.models import Artifakt, schemas


@view_config(route_name='artifacts', renderer='artifakt:templates/artifacts.jinja2')
def artifacts(_):
    return {'artifacts': DBSession.query(Artifakt).order_by(Artifakt.created.desc()).all()}


@view_config(route_name='artifacts_json', renderer='json')
def artifacts_json(_):
    return {'artifacts': [schemas['artifakt'].dump(a).data for a in DBSession.query(Artifakt).all()]}


def get_artifact(request):
    if "sha1" not in request.matchdict:
        raise HTTPBadRequest("Missing sha1 argument")
    sha1 = request.matchdict["sha1"]
    try:
        return DBSession.query(Artifakt).filter(Artifakt.sha1 == sha1).one()
    except NoResultFound:
        raise HTTPNotFound("No artifact with sha1 {} found".format(sha1))


@view_config(route_name='artifact', renderer='artifakt:templates/artifact.jinja2')
def artifact(request):
    return {'artifact': get_artifact(request)}


@view_config(route_name='artifact_json', renderer='json')
def artifact_json(request):
    return schemas['artifakt'].dump(get_artifact(request)).data


@view_config(route_name='artifact_delete')
def artifact_delete(request):
    af = get_artifact(request)
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
    disk_name = af.file
    file_name = af.filename
    mime, encoding = mimetypes.guess_type(file_name)
    if mime is None:
        mime = 'application/octet-stream'
    # If the current simple approach proves to be a problem the discussion
    # at http://stackoverflow.com/q/93551/11722 can be considered.
    response = FileResponse(disk_name, request=request, content_type=mime)
    response.content_disposition = '{}; filename="{}"'.format('inline' if inline else 'attachment', file_name)
    return response


@view_config(route_name='artifact_view', renderer="artifakt:templates/artifact_highlight.jinja2")
def artifact_inline_view(request):
    af = get_artifact(request)
    return {'content': af.file_content}


@view_config(route_name='artifact_view_archive', renderer="artifakt:templates/artifact_archive.jinja2")
def artifact_archive_view(request):
    af = get_artifact(request)
    file_name = af.filename
    mime, encoding = mimetypes.guess_type(file_name)
    ret = defaultdict(list)
    if mime == "application/x-tar":
        with tarfile.open(af.file) as tar:
            ret['tarfiles'] = tar.getmembers()
            return ret
    if mime == "application/zip":
        with zipfile.ZipFile(af.file) as _zip:
            ret['zipfiles'] = _zip.infolist()
            return ret
    return {"error": "Mimetype {} is not a known/supported archive".format(mime)}
