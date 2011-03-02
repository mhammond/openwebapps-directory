import os
import logging
import random
import time
from webob import Request, Response, html_escape
from urllib import quote as url_quote
from webob import exc
import hmac
try:
    from hashlib import sha1 as sha
except ImportError:
    import sha
import base64
import tempfile
from paste.util.ip4 import IP4Range, ip2int
from tempita import HTMLTemplate
from devauth.htpasswd import check_password, NoSuchUser

__all__ = ['DevAuth', 'make_middleware']

class DevAuth(object):
    """
    This is an authentication middleware for developer tools.

    This looks for two things for authentication: the IP address and a
    login.  The login form is presented on (unless you override it)
    ``/.devauth/login``.  This system does not present nice login
    forms, it does not redirect you to a login when you need access.
    You must know where to find the login.

    Once you've logged in ``environ['x-wsgiorg.developer_user']`` will
    be set.
    """

    secret_length = 100

    def __init__(self, app, allow="127.0.0.1", deny=None,
                 password_file=None, password_checker=None,
                 secret_file='$TMP/devauth.txt', secret=None,
                 logger='DevAuth', login_mountpoint='/.devauth',
                 expiration=None):
        """
        Parameters:

        ``app``: the application to be wrapped

        ``allow``: a set of IP addresses that are allowed (None for
        all).  This can be a list or string, and can contain IP
        addresses, IP ranges, or IPs plus a mask.

        ``deny``: a set of IP addresses that are denied, even if they
        would otherwise be allowed by ``allow``.

        ``password_file``: a password file, in the same format as
        produced by the Apache ``htpasswd`` program.

        ``password_checker``: instead of a password file, you can pass
        in a custom function that checks passwords.  This function has
        the signature ``password_checker(username, password)`` and
        returns true or false.

        ``secret_file``: a file where the server-side secret will be
        kept.  If this file doesnt exist it will be created and random
        content will be inserted.  If you put $TMP in the name of the
        file, it will be replaced by the temporary directory (which is
        read from several possible environmental variables, or
        defaults to ``/tmp``).

        ``secret``: instead of storing a secret in a file, you can
        provide the secret at instantiation.

        ``logger``: The name of the ``logging`` logger.

        ``login_mountpoint``: This is the path intercepted for the login form.

        ``expiration``: The number of minutes that a login will be
        validated.  Expiration is absolute, not based on your last
        login.  So if you give 3600, you will have to re-login every hour.
        """
        self.app = app
        logger = logger or 'DevAuth'
        if isinstance(logger, basestring):
            logger = logging.getLogger(logger)
        self.logger = logger
        self.allow = convert_ip_mask(allow)
        self.deny = convert_ip_mask(deny)
        if password_checker and password_file:
            raise TypeError(
                "You may give only one of password_checker and password_file")
        if not password_checker and not password_file:
            raise TypeError(
                "You must give one of password_checker or password_file")
        self.password_checker = password_checker
        self.password_file = password_file
        self.password_mtime = None
        if secret is None:
            secret_file = secret_file.replace('$TMP', tempfile.gettempdir())
            secret = self.read_or_create_secret(secret_file)
        self.secret = secret
        self.login_mountpoint = login_mountpoint.rstrip('/')
        self.expiration = expiration

    def read_or_create_secret(self, filename):
        """
        Read the secret from a file, or if the file doesn't exist then
        put a random secret into it.
        """
        if not os.path.exists(filename):
            secret = self.create_secret()
            if not os.path.exists(os.path.dirname(filename)):
                self.logger.info('Creating directory %s' % os.path.dirname(filename))
                os.makedirs(os.path.dirname(filename))
            f = open(filename, 'wb')
            f.write(secret)
            f.close()
            os.chmod(filename, 0600)
            self.logger.info('Wrote new secret to %s' % filename)
        else:
            try:
                f = open(filename, 'rb')
            except:
                self.logger.fatal('Cannot read secret from secret file %s' % filename)
                raise
            secret = f.read()
            f.close()
            self.logger.debug('Read secret from %s' % filename)
        return secret

    def create_secret(self):
        """
        Generate a random secret.
        """
        if hasattr(os, 'urandom'):
            bytes = os.urandom(self.secret_length)
        else:
            bytes = ''.join(chr(random.randint(0, 255)) for i in xrange(self.secret_length))
        bytes = b64encode(bytes)
        return bytes

    def __call__(self, environ, start_response):
        """
        The WSGI interface.
        """
        req = Request(environ)
        try:
            if req.path_info.startswith(self.login_mountpoint + '/login'):
                return self.login(req)(environ, start_response)
            if req.path_info.startswith(self.login_mountpoint + '/logout'):
                return self.logout(req)(environ, start_response)
            if req.cookies.get('__devauth'):
                username = self.read_cookie(req, req.str_cookies['__devauth'])
                if username and not self.check_ip(req):
                    self.logger.warning(
                        'User %r tried to log in from bad IP %s (X-Forwarded-For: %s)' % (
                        username,
                        req.remote_addr,
                        req.headers.get('X-Forwarded-For', 'not provided')))
                    username = None
                if username:
                    environ['x-wsgiorg.developer_user'] = username
        except exc.HTTPException, e:
            return e(environ, start_response)
        return self.app(environ, start_response)

    def read_cookie(self, req, cookie):
        """
        Read the username from the cookie, and check that the cookie
        is valid.  Returns None if the cookie is not valid.
        """
        try:
            username, ip, timestamp, signature = cookie.split('|', 3)
        except ValueError:
            self.logger.info("Invalid cookie (not enough |'s): %r" % cookie)
            return None
        try:
            timestamp = int(timestamp)
        except ValueError, e:
            self.logger.info('Invalid cookie, bad timestamp %r: %s' % (timestamp, e))
            return None
        if ip != req.remote_addr:
            self.logger.info('Invalid cookie; was for IP %s, requested from IP %s: %r'
                              % (ip, req.remote_addr, cookie))
            return None
        if self.expiration and timestamp + (self.expiration*60) < time.time():
            ## FIXME: not sure what to do here?  Ignore?  Redirect?
            url = req.application_url + self.login_mountpoint + '/login?msg=expired&back=%s' % url_quote(req.url)
            raise exc.HTTPTemporaryRedirect(location=url).exception
        text = '%s|%s|%s' % (username, ip, timestamp)
        hash = b64encode(hmac.new(username, text, sha).digest())
        if hash != signature:
            self.logger.info('Invalid signature: %r' % signature)
            return None
        return username

    def create_cookie(self, req, username):
        """
        Create a login cookie for the given username.
        """
        timestamp = str(int(time.time()))
        text = '%s|%s|%s' % (username, req.remote_addr, timestamp)
        hash = b64encode(hmac.new(username, text, sha).digest())
        return '%s|%s' % (text, hash)

    def check_ip(self, req):
        """
        Check that the IP address of the request if valid.  This
        checks both REMOTE_ADDR, and if it is presented
        X-Forwarded-For.  If either isn't valid then the request is
        rejected.
        """
        ip = req.remote_addr
        if not self._check_single_ip(ip):
            return False
        ip = req.headers.get('X-Forwarded-For')
        if ip and not self._check_single_ip(ip):
            return False
        return True

    def _check_single_ip(self, ip):
        ip = ip2int(ip)
        if self.deny:
            for ip_mask in self.deny:
                if ip in ip_mask:
                    return False
        if self.allow:
            for ip_mask in self.allow:
                if ip in ip_mask:
                    return True
        return False

    def login(self, req):
        """
        The login form.
        """
        if not self.check_ip(req):
            template = HTMLTemplate.from_filename(os.path.join(os.path.dirname(__file__), 'ip_denied.html'))
            return Response(template.substitute(req=req), status='403 Forbidden')
        if req.method == 'POST':
            username = req.str_POST['username']
            password = req.str_POST['password']
            if not self.check_login(username, password):
                msg = 'Invalid username or password'
            else:
                resp = exc.HTTPFound(location=req.params.get('back') or req.application_url)
                resp.set_cookie('__devauth', self.create_cookie(req, username))
                return resp
        else:
            msg = req.params.get('msg')
        back = req.params.get('back') or req.application_url
        if msg == 'expired':
            msg = 'Your session has expired.  You can log in again, or just <a href="%s">return to your previous page</a>' % (
                html_escape(back))
        template = HTMLTemplate.from_filename(os.path.join(os.path.dirname(__file__), 'login.html'))
        resp = Response(template.substitute(req=req, msg=msg, back=back, middleware=self))
        try:
            if req.cookies.get('__devauth'):
                self.read_cookie(req, req.str_cookies['__devauth'])
        except exc.HTTPException:
            # This means the cookie is invalid
            resp.delete_cookie('__devauth')
        return resp

    def check_login(self, username, password):
        if self.password_checker is not None:
            return self.password_checker(username, password)
        else:
            try:
                return check_password(username, password, self.password_file)
            except NoSuchUser:
                return False

    def logout(self, req):
        """
        Logout
        """
        back = req.GET.get('back', '/')
        resp = exc.HTTPFound(location=back)
        resp.delete_cookie('__devauth')
        return resp

def b64encode(s, altchars='_-'):
    """
    base64 encoding, without newlines or +/
    """
    return base64.b64encode(s, altchars).replace('\n', '').replace('\r', '')

def convert_ip_mask(setting):
    if not setting:
        return None
    if isinstance(setting, basestring):
        setting = setting.split()
    result = []
    for item in setting:
        if isinstance(item, basestring):
            item = IP4Range(item)
        result.append(item)
    return result

def make_middleware(app, global_conf, allow=None, deny=None,
                    password_file=None, secret_file='/tmp/devauth.txt',
                    secret=None, logger=None, expiration=None,
                    login_mountpoint='/.devauth'):
    allow = convert_ip_mask(allow)
    deny = convert_ip_mask(deny)
    if not allow and not deny and not password_file:
        raise ValueError(
            "You must provide at least one of allow, deny, or password_file")
    if isinstance(expiration, basestring):
        expiration = int(expiration)
    return DevAuth(app, allow=allow, deny=deny, password_file=password_file,
                   secret_file=secret_file, secret=None, logger=logger,
                   expiration=expiration, login_mountpoint=login_mountpoint)

make_middleware.__doc__ == DevAuth.__doc__
