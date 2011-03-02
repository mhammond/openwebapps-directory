import os
import sys
import site

base = os.path.dirname(os.path.dirname(__file__))

site.addsitedir(os.path.join(base, 'vendor'))

sys.path.insert(0, base)

_application = None

def application(environ, start_response):
    global _application
    if _application is not None:
        return _application(environ, start_response)
    if environ.get('APPDIR_CONFIG'):
        filename = environ['APPDIR_CONFIG']
        from paste.deploy.loadwsgi import loadapp
        _application = loadapp('config:' + filename)
    else:
        from directory import wsgiapp
        _application = wsgiapp.Application(
            db=None,
            search_paths=None,
            site_title=None)
    return _application(environ, start_response)
