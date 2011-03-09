import os
from directory.wsgiapp import WSGIApp
from directory.util import get_template_search_paths

__all__ = ['make_app']


def make_app(global_conf=None, db=None, search_paths=None,
             include_static=False, debug=False,
             site_title=None, jsapi_location=None,
             admin_htpasswd=None, admin_allow=None, admin_deny=None,
             create_on_startup=False):
    if not db:
        db = 'sqlite:///directory.sqlite'
    if search_paths:
        if isinstance(search_paths, basestring):
            search_paths = [s.strip() for s in search_paths.splitlines()
                            if s.strip()]
    else:
        search_paths = []
    search_paths = get_template_search_paths(search_paths)
    if isinstance(include_static, basestring):
        from paste.deploy.converters import asbool
        include_static = asbool(include_static)
    if isinstance(create_on_startup, basestring):
        from paste.deploy.converters import asbool
        create_on_startup = asbool(create_on_startup)
    app = WSGIApp(db, search_paths, site_title=site_title,
                  jsapi_location=jsapi_location)
    if create_on_startup:
        app.update_db()
    if include_static:
        from paste.urlparser import StaticURLParser
        from paste.urlmap import URLMap
        from paste.cascade import Cascade
        static_apps = []
        for path in search_paths:
            static_apps.append(StaticURLParser(
                os.path.join(path, 'static')))
        static_app = Cascade(static_apps)
        mapping = URLMap()
        mapping['/static'] = static_app
        mapping[''] = app
        app = mapping
    if isinstance(debug, basestring):
        from paste.deploy.converters import asbool
        debug = asbool(debug)
    if admin_htpasswd:
        from devauth import DevAuth
        app = DevAuth(app, allow=admin_allow, deny=admin_deny,
                      password_file=admin_htpasswd,
                      login_mountpoint='/.mozilla')
    if debug:
        try:
            from weberror.evalexception import EvalException
        except ImportError:
            try:
                from werkzeug.debug import DebuggedApplication
            except ImportError:
                from paste.evalexception import EvalException
                app = EvalException(app)
            else:
                app = DebuggedApplication(app, evalex=True)
        else:
            app = EvalException(app)
    return app
