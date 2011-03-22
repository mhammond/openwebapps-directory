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
from directory.util import make_slug, get_template_search_paths, json, atom_date
from directory import httpget
import jinja2
from datetime import datetime
import dateutil
import urllib2


class WSGIApp(object):

    map = Mapper()
    map.connect('home', '/', method='index')
    map.connect('add', '/add', method='add')
    map.connect('build', '/build', method='build')
    map.connect('view_app', '/app/{origin}/{slug}', method='view_app')
    map.connect('about', '/about', method='about')
    map.connect('search', '/search', method='search')
    map.connect('keyword', '/keyword/{keyword}', method='view_keywords')
    map.connect('keywords', '/keyword/', method='all_keywords')
    map.connect('admin_app', '/app/{origin}/{slug}/admin', method='admin_app')
    map.connect('keyword_admin', '/admin/keywords', method='admin_keywords')
    map.connect('email_admin', '/admin/emails', method="admin_emails")
    map.connect('update_db', '/.update-db', method='update_db')
    map.connect('feed', '/feed.atom', method='feed')

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

    @wsgify
    def __call__(self, req):
        results = self.map.routematch(environ=req.environ)
        if not results:
            return exc.HTTPNotFound()
        match, route = results
        link = URLGenerator(self.map, req.environ)
        req.urlvars = ((), match)
        if match['method'] == 'update_db':
            return self.update_db(req)
        handler = Handler(self, req, link, match)
        return handler.respond()

    def update_db(self, req=None):
        model.Base.metadata.create_all(self.engine)
        from directory.migrate import update_database
        update_database(self.engine)
        return 'ok'


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
                format_date=self.format_date,
                atom_date=atom_date,
                urljoin=urlparse.urljoin))
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
        featured_apps = model.Application.featured_apps(hidden=self.is_admin()).all()
        keywords = [k.word for k in model.Keyword.all_words()]
        recent_apps = model.Application.recent(6, hidden=self.is_admin()).all()
        return self.render('index', featured_apps=featured_apps,
                           keywords=keywords, recent_apps=recent_apps)

    def add(self):
        errors = {}
        check_message = None
        if (self.req.method == 'POST'
            and self.req.params.get('remove_manifest_url')):
            return self.remove_app()
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
        content_type, raw_data = httpget.get(manifest_url)
        if content_type != validator.content_type:
            errors['content_type'] = content_type
            errors['content_type_wanted'] = validator.content_type
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

    def remove_app(self):
        manifest_url = self.req.params['remove_manifest_url']
        message = None
        try:
            httpget.get(manifest_url)
        except urllib2.HTTPError, e:
            if e.code not in (404, 410):
                message = 'The url must return 404 or 410 (got %s)' % e.code
        else:
            message = 'The url still exists'
        app = model.Application.by_manifest_url(
            manifest_url, session=self.session)
        if app is None:
            message = 'No application is registered with that URL'
        if message:
            return self.render('add', remove_error=message)
        self.session.delete(app)
        ## FIXME: note the delete properly
        return 'deleted'

    def build(self):
        p = self.req.params
        manifest = None
        origin = None
        if 'url' in p and 'has_manifest' not in p:
            manifest = self._guess_manifest(p['url'])
            origin = get_origin(p['url'])
        elif 'has_manifest' in p:
            pass
        return self.render('build', manifest=manifest, origin=origin,
                           content_type=validator.content_type)

    def _guess_manifest(self, url):
        content_type, content = httpget.get(url)
        print url, content_type
        if content_type.lower() in (validator.content_type, 'application/json'):
            data = json.loads(content)
            return data
        import lxml.html
        page = lxml.html.parse(url).getroot()
        name = page.cssselect('title')
        if name:
            name = name[0].text_content()
        else:
            name = 'unknown'
        keywords = page.cssselect('meta[name=keywords]')
        if keywords:
            keywords = [k.strip() for k in keywords.get('content', '').split(',')]
        else:
            keywords = []
        desc = page.cssselect('meta[name=description]')
        if desc:
            desc = desc.get('content').strip()
        else:
            desc = ''
        icons = {}
        icon = page.cssselect('link[rel*=icon]')
        if icon:
            ## FIXME: how do I get the size?
            icons['32'] = icon[0].get('href')
        else:
            favicon_url = get_origin(url) + '/favicon.ico'
            try:
                content_type, icon_file = httpget.get(favicon_url)
            except:
                pass
            else:
                if icon_file:
                    icons['32'] = favicon_url

        manifest = {
            'name': name,
            'description': desc,
            'launch_path': urlparse.urlsplit(url).path or '/',
            'icons': icons,
            'experimental': {'keywords': keywords},
            }
        return manifest

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
            app.hide = bool(p.get('hide'))
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
            keywords = p.get('keywords') or ''
            keywords = [k.strip() for k in keywords.split(',')
                        if k.strip()]
            app.keywords = keywords
            model.Keyword.add_words(keywords, session=self.session)
            self.session.add(app)
            self.session.commit()
            return exc.HTTPFound(app.url + '/admin')
        return self.render('admin_app', app=app)

    def admin_keywords(self):
        if not self.is_admin():
            raise exc.HTTPNotFound
        s = self.session
        keywords = s.query(model.Keyword).order_by(model.Keyword.word).all()
        trimmed = None
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
            if self.req.params.get('trim'):
                trimmed = model.Keyword.trim_keywords(self.session)
            s.commit()
        return self.render('admin_keywords', keywords=keywords,
                           trimmed=trimmed)

    def admin_emails(self):
        if not self.is_admin():
            raise exc.HTTPNotFound
        apps = [
            (app.manifest, app)
            for app in self.session.query(model.Application)]
        return self.render('admin_emails', apps=apps)

    def search(self):
        q = self.req.GET.get('q')
        if q:
            results = model.Application.search(q, hidden=self.is_admin()).all()
        else:
            results = None
        return self.render('search', results=results, q=q)

    def view_keywords(self, keyword):
        apps = model.Application.search_keyword(keyword, hidden=self.is_admin())
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

    def feed(self):
        apps = model.Application.recent(10)
        return Response(body=self.render('feed.xml', apps=apps),
                        content_type='application/atom+xml')
