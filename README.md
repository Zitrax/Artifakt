Artifakt
========

Artifact / File server - makes it easy to track customer deliveries or just a place to dump important files.

Features
--------

* Files can be stored on the server either as single files or in bundles.
* The same file is not stored twice, content is tracked by their sha1 sums.
* Archive file list can be viewed.
* Text/code files can be viewed with syntax highlighting.
* Each file or bundle can be marked as delivered to a specific customer.
* Each file or bundle has threaded comments.
* The version control system origin of each file can be stored.
* Search functionality.

Getting Started
---------------

- `python setup.py develop` ( Recommended to use virtualenv )

SQLite:
  - Verify that sqlalchemy.url in development.ini looks something like: sqlite:///%(here)s/artifakt.sqlite

MySQL:
  - Enable mysqlclient in setup.py before running it.
  - Create a new database named 'artifaktdb' in mysql
  - Use the following command: CREATE DATABASE artifaktdb CHARACTER SET utf8;

- `initialize_artifakt_db development.ini`

- `pserve development.ini`

## Settings

Some important settings to look at before running Artifakt.

### `artifakt/artifakt.yaml`
* There are some hardcoded security strings in artifakt/artifakt.yaml. You should update them in a production setup.

### `production.ini` / `development.ini`
* `artifakt.storage`: This points to the directory where all artifacts are stored. 
* `hosts`: The address of the server.
* `port`: The port of the server.
#### Settings needed for sending mails
* `mail.host`: The smtp host name
* `mail.port`: The smtp port
* `mail.queue_path`: Path to a directory where queued emails are stored
* `mail.default_sender`: Sender address of emails from the system

To actually send the mails `qp` must be run periodically.

## Info

[![Build Status](https://travis-ci.org/Zitrax/Artifakt.svg?branch=master)](https://travis-ci.org/Zitrax/Artifakt)
[![Coverage Status](https://coveralls.io/repos/github/Zitrax/Artifakt/badge.svg?branch=master)](https://coveralls.io/github/Zitrax/Artifakt?branch=master)
