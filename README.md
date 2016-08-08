Note - still work in progress... !


artifakt README
==================

Getting Started
---------------

- cd <directory containing this file>

- $VENV/bin/python setup.py develop

MySQL:
  - Create a new database named 'artifaktdb' in mysql
  - Use the following command: CREATE DATABASE artifaktdb CHARACTER SET utf8;
SQLite:
  - Replace sqlalchemy.url in development.ini with something like: sqlite:///%(here)s/artifakt.sqlite
  - Can also comment out mysql in setup.py before running it

- $VENV/bin/initialize_artifakt_db development.ini

- $VENV/bin/pserve development.ini

## Info

[![Build Status](https://travis-ci.org/Zitrax/Artifakt.svg?branch=master)](https://travis-ci.org/Zitrax/Artifakt)
