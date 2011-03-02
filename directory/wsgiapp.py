import os
import urlparse
import codecs
from webob.dec import wsgify
from webob import exc
from webob import Response
from routes import Mapper, URLGenerator
from directory import model
from directory import validator
from directory.util import get_origin, format_description, clean_unicode
from directory.util import make_slug, get_template_search_paths, json
import urllib2
import jinja2
from datetime import datetime
import dateutil


class WSGIApp(object):

    map = Mapper()
    map.connect('home', '/', method='index')
    map.connect('add', '/add', method='add')
    map.connect('view_app', '/app/{origin}/{slug}', method='view_app')
    map.connect('about', '/about', method='about')
    map.connect('search', '/search', method='search')
    map.connect('keyword', '/keyword/{keyword}', method='view_keywords')
    map.connect('keywords', '/keyword/', method='all_keywords')
    map.connect('admin_app', '/app/{origin}/{slug}/admin', method='admin_app')
    map.connect('keyword_admin', '/admin/keywords', method='admin_keywords')

    def __init__(self, db, search_paths=None,
                 site_title=None,
                 jsapi_location=None):
        self.setup_db(db)
        if not search_paths:
            search_paths = get_template_search_paths(search_paths)
        self.jinja_loader = jinja2.FileSystemLoader(search_paths)
        self.jinja_env = jinja2.Environment(
            trim_blocks=True,
            autoescape=True,
            loader=self.jinja_loader,
            auto_reload=True,
            )
        self.site_title = site_title or 'Application Directory'
        self.jsapi_location = jsapi_location or 'https://myapps.mozillalabs.com'

    def setup_db(self, db):
        self.db = db
        from sqlalchemy import create_engine
        kw = {}
        if self.db.startswith('mysql:'):
            kw['pool_recycle'] = 3600
        self.engine = create_engine(self.db, **kw)
        model.Session.configure(bind=self.engine)
        model.Base.metadata.create_all(self.engine)

    @wsgify
    def __call__(self, req):
        results = self.map.routematch(environ=req.environ)
        if not results:
            return exc.HTTPNotFound()
        match, route = results
        link = URLGenerator(self.map, req.environ)
        req.urlvars = ((), match)
        handler = Handler(self, req, link, match)
        return handler.respond()


class Handler(object):

    def __init__(self, app, req, link, match):
        self.app = app
        self.req = req
        self.link = link
        self.match = match
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = model.Session()
        return self._session

    def respond(self):
        kwargs = self.match.copy()
        method = kwargs.pop('method')
        method = getattr(self, method)
        try:
            result = method(**kwargs)
        except:
            if self._session:
                self._session.rollback()
            raise
        else:
            if self._session:
                self._session.commit()
        return result

    def render(self, template_name, **args):
        template_class = make_slug(template_name)
        if not os.path.splitext(template_name)[1]:
            template_name += '.html'
        tmpl = self.app.jinja_env.get_template(
            template_name,
            globals=dict(
                req=self.req,
                handler=self,
                app_config=self.app,
                sorted=sorted,
                isinstance=isinstance,
                list=list,
                app_html=self.app_html,
                format_description=format_description,
                template_class=template_class,
                format_date=self.format_date))
        return tmpl.render(**args)

    def get_app(self, origin_key, session=None):
        app = model.Application.get(origin_key, session=session)
        if app is None:
            raise exc.HTTPNotFound('No such application')
        return app

    def app_html(self, app, **options):
        return jinja2.Markup(self.render('one_app', app=app, **options))

    def is_admin(self):
        return bool(self.req.environ.get('x-wsgiorg.developer_user'))

    def format_date(self, date):
        if not date:
            return ''
        return date.strftime('%Y-%m-%d %H:%M:%S %Z')

    ## Actual views:

    def index(self):
        featured_apps = model.Application.featured_apps().all()
        keywords = [k.word for k in model.Keyword.all_words()]
        recent_apps = model.Application.recent(4).all()
        return self.render('index', featured_apps=featured_apps,
                           keywords=keywords, recent_apps=recent_apps)

    def add(self):
        errors = {}
        check_message = None
        if self.req.method == 'POST':
            check_message, errors, resp = self._add_application()
            if resp is not None:
                return resp
        ## FIXME: instead of this text/html test, should I just have
        ## another flag?
        if errors and 'text/html' not in self.req.accept:
            # text/plain then!
            return Response(
                self.render('errors.txt', errors=errors),
                content_type='text/plain',
                status=400)
        elif check_message and 'text/html' not in self.req.accept:
            return Response(
                check_message,
                content_type='text/plain',
                status=200)
        return self.render('add', errors=errors, check_message=check_message)

    def _add_application(self):
        url = self.req.params['manifest_url']
        manifest, raw_data, errors = self._get_manifest(url)
        if errors:
            errors['url'] = url
            errors['raw_data'] = raw_data
            errors['manifest'] = manifest
            extra_errors = []
            errors = clean_unicode(errors, extra_errors.append)
            if extra_errors:
                errors['unicode'] = extra_errors
            return None, errors, None
        if not errors:
            origin = get_origin(url)
            app = model.Application.by_origin(origin, session=self.session)
            if self.req.params.get('dontadd'):
                if app is None:
                    check_message = 'Your new application is ready and valid!'
                else:
                    check_message = 'Your application update is ready and valid!'
                return check_message, errors, None
            if app is None:
                app = model.Application.from_manifest(
                    manifest, datetime.now(), url, origin,
                    session=self.session)
            else:
                app.update_from_manifest(
                    manifest, datetime.now(), url, origin,
                    session=self.session)
            url = urlparse.urljoin(self.req.url, app.url)
            resp = Response(
                url, location=app.url, status=302,
                content_type='text/plain')
            return None, None, resp

    def _get_manifest(self, manifest_url):
        errors = {}
        resp = urllib2.urlopen(manifest_url)
        content_type = resp.info().getheader('content-type')
        if content_type != validator.content_type:
            errors['content_type'] = content_type
            errors['content_type_wanted'] = validator.content_type
        raw_data = resp.read()
        ## FIXME: should try to figure out the encoding better
        if raw_data.startswith(codecs.BOM_UTF8):
            raw_data = raw_data[len(codecs.BOM_UTF8):]
        try:
            raw_data = raw_data.decode('utf8')
        except UnicodeDecodeError, e:
            errors['unicode'] = e
            raw_data = raw_data.decode('utf8', 'replace')
        manifest = None
        try:
            manifest = json.loads(raw_data.strip())
        except Exception, e:
            errors['json_parse'] = unicode(e)
        if manifest:
            error_log = validator.validate(manifest)
            if error_log:
                errors['error_log'] = error_log
        return manifest, raw_data, errors

    def view_app(self, origin, slug):
        app = self.get_app(origin)
        return self.render('view_app', app=app)

    def admin_app(self, origin, slug):
        if not self.is_admin():
            raise exc.HTTPNotFound
        app = self.get_app(origin, session=self.session)
        if self.req.method == 'POST':
            p = self.req.params
            if p.get('delete'):
                self.session.delete(app)
                self.session.commit()
                return 'Deleted!'
            app.featured = bool(p.get('featured'))
            if p.get('featured_sort'):
                app.featured_sort = float(p['featured_sort'])
            else:
                app.featured_sort = None
            if p.get('featured_start'):
                app.featured_start = dateutil.parse(p['featured_start'])
            else:
                app.featured_start = None
            if p.get('featured_end'):
                app.featured_end = dateutil.parse(p['featured_end'])
            else:
                app.featured_end = None
            self.session.add(app)
            self.session.commit()
            return exc.HTTPFound(app.url + '/admin')
        return self.render('admin_app', app=app)

    def admin_keywords(self):
        if not self.is_admin():
            raise exc.HTTPNotFound
        s = self.session
        keywords = s.query(model.Keyword).order_by(model.Keyword.word).all()
        by_word = dict(
            (k.word, k) for k in keywords)
        if self.req.method == 'POST':
            # Since unchecked items don't show up, first we unhide everything
            for k in keywords:
                k.hidden = False
            for name, value in self.req.params.items():
                if name.startswith('keyword_hide_'):
                    word = name[len('keyword_hide_'):]
                    by_word[word].hidden = True
                elif name.startswith('keyword_description_'):
                    word = name[len('keyword_description_'):]
                    by_word[word].description = value.strip() or None
            for k in keywords:
                s.add(k)
            s.commit()
        return self.render('admin_keywords', keywords=keywords)

    def search(self):
        q = self.req.GET.get('q')
        if q:
            results = model.Application.search(q).all()
        else:
            results = None
        return self.render('search', results=results, q=q)

    def view_keywords(self, keyword):
        apps = model.Application.search_keyword(keyword)
        k = model.Keyword.get(keyword)
        if k is None:
            # This doesn't exist
            return exc.HTTPNotFound('No keyword found')
        return self.render('view_keywords', apps=apps, keyword=keyword,
                           description=k.description)

    def all_keywords(self):
        keywords = [k.word for k in model.Keyword.all_words()]
        return self.render('all_keywords', keywords=keywords)

    def about(self):
        return self.render('about')
