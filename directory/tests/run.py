import doctest
import os
import sys
import site
import warnings

warnings.filterwarnings("error")

here = os.path.dirname(os.path.abspath(__file__))


def setup_path():
    base = os.path.dirname(os.path.dirname(here))
    if base not in sys.path:
        sys.path.insert(0, base)
    vendor = os.path.join(base, 'vendor')
    if vendor not in sys.path:
        site.addsitedir(vendor)


def main():
    flags = doctest.ELLIPSIS
    if '-u' in sys.argv:
        flags = flags | doctest.REPORT_UDIFF
    if '-x' in sys.argv:
        flags = flags | doctest.REPORT_ONLY_FIRST_FAILURE
    for fn in os.listdir(here):
        if fn.endswith('.txt') and fn.startswith('test_'):
            doctest.testfile(fn, optionflags=flags,
                             globs=init_app())


def init_app():
    from directory.configure import make_app
    if os.path.exists('test_directory.sqlite'):
        os.unlink('test_directory.sqlite')
    simple_templates = os.path.join(os.path.dirname(here), 'simple-templates')
    wsgi_app = make_app(db='sqlite:///test_directory.sqlite',
                        include_static=True,
                        search_paths=[simple_templates],
                        create_on_startup=True)
    from webtest import TestApp
    app = TestApp(wsgi_app)
    import directory.httpget
    if directory.httpget._override != getter:
        directory.httpget._override = getter
    return dict(
        wsgi_app=wsgi_app,
        app=app,
        add_resource=add_resource)


_resources = {}


def getter(url):
    if url in _resources:
        obj = _resources[url]
        if isinstance(obj, Exception):
            raise obj
        return obj
    return None


def add_resource(url, body, content_type=None):
    if isinstance(body, Exception):
        _resources[url] = body
    else:
        if content_type is None:
            from directory import validator
            content_type = validator.content_type
        _resources[url] = (content_type, body)


if __name__ == '__main__':
    setup_path()
    main()
