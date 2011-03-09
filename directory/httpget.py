"""Simple HTTP getter

With mockability!
"""
import urllib2

_override = None


def get(manifest_url):
    if _override:
        result = _override(manifest_url)
        if result is not None:
            return result
    resp = urllib2.urlopen(manifest_url)
    content_type = resp.info().getheader('content-type') or 'application/octet-stream'
    return content_type, resp.read()
