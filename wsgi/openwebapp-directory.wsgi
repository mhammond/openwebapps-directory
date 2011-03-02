import os
import sys
import site

base = os.path.dirname(os.path.dirname(__file__))

site.addsitedir(os.path.join(base, 'vendor'))

sys.path.insert(0, base)

from directory import wsgiapp
application = wsgiapp.Application(
    db=None,
    search_paths=None,
    site_title=None)
