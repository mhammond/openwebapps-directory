# Open Web Apps Reference Directory

This is an example of how you might create an application directory
for listing Open Web Applications.  It's meant to be a simple implementation that may be suitable to build on, or may just be an example you can consider as you decide how to design your own system.

## How The Application Is Setup

There are only a couple pieces:

- The database models are in `directory/model.py`.  This is a very simple database setup using [SQLAlchemy](http://www.sqlalchemy.org/), and works with SQLite, MySQL, or PostgreSQL.

- The application logic is in `directory/wsgiapp.py`.  This includes a very small framework-like system, and some methods for specific pages.

- The base templates are in `directory/simple-templates/`.  These create a *very boring* but functional directory.  If you want to create your own style these are a good starting place.  The templates all use [Jinja2](http://jinja.pocoo.org/).

- Fancier templates are in `directory/templates/`.  These make our actual site.

- Static files are in `directory/{template_dir}/static/` -- they go with the look of the site.  There's very little Javascript.

## Dependencies and Libraries

The dependencies are all in the `vendor/` directory.  This directory has to be added to `sys.path` to run the application; you can do that with `$PYTHONPATH` or using [virtualenv](http://virtualenv.openplans.org).

This code expects you to use Python 2.6.  Python 2.7 should work fine, 2.5 probably won't work (just because it's not tested), and Python 3.x *will not* work.

## Management tasks

Some notes if you want to actually extend this code.

To set everything up nicely for development run:

- Create a virtualenv environment at this root
- Link `vendor/add-path.pth.link` to `lib/python2.6/site-packages/add-path.pth`
- Install compiled libraries with `pip install -r compiled-requirements.txt`
- Install new vendor libraries with `pip install --install-option="--install-lib=HERE/vendor" PACKAGE`
