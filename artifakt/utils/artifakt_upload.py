import argparse
import re

import requests

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Upload file to the Artifakt server.')
    parser.add_argument('--server', help='The URL of the Artifakt server', required=True)
    parser.add_argument('--file', help='The file to upload', required=True)
    parser.add_argument('--email', help='The email of the upload user', required=True)
    parser.add_argument('--pwd', help='The password of the upload user', required=True)

    args = parser.parse_args()
    print(args)

    # Trim trailing / if passed
    if args.server[-1] == '/':
        args.server = args.server[:-1]

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
    print("Uploading...")
    upload_page = args.server + "/upload"
    with open(args.file, 'rb') as f:
        files = {'file': f}
        r = requests.post(upload_page, cookies=r.cookies, files=files, allow_redirects=False,
                          data={'metadata': '{}'})
    print(r.text)
    r.raise_for_status()
