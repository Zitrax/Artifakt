import argparse
import json
import re

import requests

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload file to the Artifakt server.')

    # Required
    parser.add_argument('--server', help='The URL of the Artifakt server', required=True)
    parser.add_argument('--file', help='The file to upload', required=True)
    parser.add_argument('--email', help='The email of the upload user', required=True)
    parser.add_argument('--pwd', help='The password of the upload user', required=True)

    # Optional
    parser.add_argument('--comment', help='Artifakt comment', default='')
    parser.add_argument('--rurl', help="Repository URL", default='')
    parser.add_argument('--rname', help="Repository name", default='')
    parser.add_argument('--rtype', help="Repository type", default='')
    parser.add_argument('--rrev', help="Repository revision", default='')

    parser.add_argument('--quiet', help="Do not print to stdout", action='store_true')

    args = parser.parse_args()

    # Trim trailing / if passed
    if args.server[-1] == '/':
        args.server = args.server[:-1]

    if not args.quiet:
        print("Connecting...")
    login_page = args.server + "/login?after=%2F"
    r = requests.get(login_page, allow_redirects=False)
    r.raise_for_status()

    # Find csrf_token from response
    m = re.search('<input type="hidden" name="csrf_token" value="([0-9a-f]+)"/>', r.text)
    if not m:
        raise LookupError("Could not find csrf token in response")
    csrf_token = m.group(1)

    # Login
    if not args.quiet:
        print("Logging in...")
    r = requests.post(login_page, allow_redirects=False,
                      cookies=r.cookies, data={'email': args.email,
                                               'password': args.pwd,
                                               'csrf_token': csrf_token})
    r.raise_for_status()
    # FIXME: Should not have to parse HTML to detect this
    if re.search('Wrong e-mail or password', r.text):
        raise Exception("Wrong e-mail or password")

    # Upload
    if not args.quiet:
        print("Uploading...")
    upload_page = args.server + "/upload"
    with open(args.file, 'rb') as f:
        files = {'file': f}
        metadata = {'artifakt': {'comment': args.comment},
                    'repository': {'url': args.rurl,
                                   'name': args.rname,
                                   'type': args.rtype},
                    'vcs': {'revision': args.rrev}}
        r = requests.post(upload_page, cookies=r.cookies, files=files, allow_redirects=False,
                          data={'metadata': json.dumps(metadata)})
    if not args.quiet:
        print("Server response: " + r.text)
        print("HTTP status: " + str(r.status_code))
    r.raise_for_status()
