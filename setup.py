import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'pyramid',
    'pyramid_debugtoolbar < 4.1',  # Python 3.4 chokes on 4.1 at the moment on travis (3.5 works though)
    'pyramid_tm',
    'SQLAlchemy < 1.1',
    'transaction',
    'zope.sqlalchemy',
    'waitress',
    'pyramid_jinja2',
    'pyramid_chameleon',
    'marshmallow < 3.0.0',  # We seem to be incompatible with 3.0.0b2
    'marshmallow-sqlalchemy',
    'nose',
    'tzf.pyramid_yml',
    'pyramid_fullauth',
    'pyramid_basemodel',
    'pyramid_mailer',
    'portalocker',
    'apscheduler'
    #'mysqlclient'  # Needs libpython3.5-dev
    ]

setup(name='artifakt',
      version='0.0',
      description='artifakt',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='artifakt',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = artifakt:main
      [console_scripts]
      initialize_artifakt_db = artifakt.scripts.initializedb:main
      """,
      )
