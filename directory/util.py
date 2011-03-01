import re
import urlparse
import cgi
from jinja2 import Markup

repl_chars = re.compile(r"[ _]")
bad_chars = re.compile(r"[^a-z0-9-]")
rep_chars = re.compile(r"--+")


def make_slug(name):
    name = name.lower()
    name = repl_chars.sub('-', name)
    name = bad_chars.sub('', name)
    name = rep_chars.sub('-', name)
    return name


def get_icon(icons, origin):
    if not icons:
        return None
    ## Otherwise we just want the largest?
    options = sorted((
        (int(key), url) for key, url in icons.items()))
    if options:
        return urlparse.urljoin(origin, options[-1][1])
    return None


def get_origin(url):
    parsed = urlparse.urlsplit(url)
    ## FIXME: normalize ports:
    origin_parts = (parsed[0], parsed[1], '', '', '')
    return urlparse.urlunsplit(origin_parts)


def origin_to_key(origin):
    ## FIXME: should make sure it's ASCII too
    origin = origin.lower()
    parsed = urlparse.urlsplit(origin)
    scheme = parsed.scheme
    netloc = parsed.netloc
    if '@' in netloc:
        ## FIXME: should this ever happen or be allowed?
        netloc = netloc.split('@', 1)[1]
    port = None
    if ':' in netloc:
        netloc, port = netloc.split(':', 1)
        port = int(port)
        if port == 80 and scheme == 'http':
            port = None
        elif port == 443 and scheme == 'https':
            port = None
    key = ''
    if scheme != 'http':
        key += 'https_'
    key += netloc
    if port:
        key += '_%s' % port
    return key


def format_description(d):
    ## FIXME: handle leading whitespace
    d = cgi.escape(d)
    d = d.replace('\n', '<br />\n')
    return Markup(d)


def clean_unicode(v, reporter):
    """Handles bad unicode characters in a data structure"""
    if isinstance(v, dict):
        for key, value in v.items():
            new_value = clean_unicode(value, reporter)
            new_key = clean_unicode(key, reporter)
            if key != new_key:
                del v[key]
                v[new_key] = new_value
            else:
                v[key] = new_value
    elif isinstance(v, list):
        for i in range(len(v)):
            v[i] = clean_unicode(v[i], reporter)
    elif isinstance(v, tuple):
        v = tuple(clean_unicode(list(v), reporter))
    elif isinstance(v, str):
        try:
            v = v.decode('utf8')
        except UnicodeDecodeError, e:
            reporter('Bad string (%s): %r' % (e, v))
            ## Or use v.decode('string_escape')?
            v = v.decode('utf8', 'replace')
    return v
