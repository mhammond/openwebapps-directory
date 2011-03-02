"""
Intended to be run with nose, or py.test
"""
from devauth import DevAuth
from webtest import TestApp
import logging
logging.basicConfig(level=logging.DEBUG)

def auth_app(environ, start_response):
    """
    Test app that requires successful authentication
    """
    user = environ.get('x-wsgiorg.developer_user')
    if not user:
        start_response('403 Forbidden', [('content-type', 'text/plain')])
        return ['no allowed']
    else:
        start_response('200 OK', [('content-type', 'text/plain')])
        return ['OK %s' % user]

def password_checker(username, password):
    return username == password
        
wsgi_app = DevAuth(
    auth_app, allow='127.0.0.1/8 192.168.0.50', deny='127.0.0.5',
    password_checker=password_checker, secret='secret')
app = TestApp(wsgi_app, extra_environ={'REMOTE_ADDR': '127.0.0.1'})

def test_app():
    app.get('/', status=403)
    app.get('/', status=200, extra_environ={'x-wsgiorg.developer_user': 'test'})
    resp = login(app)
    resp.follow()
    resp = app.get('/', status=200)
    assert resp.body == 'OK bob'
    app.get('/', status=403, extra_environ={'REMOTE_ADDR': '10.1.1.1'})
    login(app, '10.1.1.1', status=403)
    login(app, '127.0.0.5', status=403)
    login(app, '127.0.0.100')
    app.get('/', status=200, extra_environ={'REMOTE_ADDR': '127.0.0.100'})
    login(app, '192.168.0.50')
    app.get('/', status=200, extra_environ={'REMOTE_ADDR': '192.168.0.50'})
    
def login(app, ip='127.0.0.1', status=200):
    app.extra_environ['REMOTE_ADDR'] = ip
    resp = app.get('/.devauth/login', status=status)
    if status != 200:
        return
    resp.form['username'] = 'bob'
    resp.form['password'] = 'bob'
    return resp.form.submit()
    
