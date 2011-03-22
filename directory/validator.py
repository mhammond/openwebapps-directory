"""Validates the manifest files"""
from directory.util import json
import posixpath
import urlparse

__all__ = ['content_type', 'validate', 'normalize']

## The expected content-type:
content_type = 'application/x-web-app-manifest+json'


def validate(manifest):
    """Validate a manifest and returns a dictionary of error messages."""
    errors = []
    if 'capabilities' in manifest and not is_dict(manifest['capabilities']):
        errors.append(
            'capabilities property must be an object (got %s)'
            % json.dumps(manifest['capabilities']))
    if 'default_locale' in manifest:
        if not is_string(manifest['default_locale']):
            errors.append(
                'default_locale property must be a string (got %s)'
                % json.dumps(manifest['default_locale']))
        elif not manifest['default_locale']:
            errors.append(
                'default_locale property must not be empty')
            ## FIXME: should test that it's a valid locale
    if 'experimental' in manifest and not is_dict(manifest['experimental']):
        errors.append(
            'experimental property must be an object (got %s)'
            % json.dumps(manifest['experimental']))
    if 'description' in manifest:
        if not is_string(manifest['description']):
            errors.append(
                'description property must be a string (got %s)'
                % json.dumps(manifest['description']))
        elif not manifest['description']:
            errors.append(
                'description property, if present, must not be empty')
        elif len(manifest['description']) >= 1024:
            errors.append(
                'description property can only be 1023 characters long (got %s characters)'
                % len(manifest['description']))
    if 'developer' in manifest:
        dev = manifest['developer']
        if not is_dict(dev):
            errors.append(
                'developer property must be an object (got %s)'
                % json.dumps(dev))
        else:
            if 'name' in dev and not is_string(dev['name']):
                errors.append(
                    'developer.name property must be a string (got %s)'
                    % json.dumps(dev['name']))
            if 'url' in dev and not is_string(dev['url']):
                errors.append(
                    'developer.url property must be a string (got %s)'
                    % json.dumps(dev['url']))
            if 'email' in dev and not is_string(dev['email']):
                errors.append(
                    'developer.email property must be a string (got %s)'
                    % json.dumps(dev['email']))
            extra = extra_keys(dev, ['name', 'url', 'email'])
            if extra:
                errors.append(
                    'The developer object has unknown keys: %s'
                    % ', '.join(extra))
    if 'icons' in manifest:
        if not is_dict(manifest['icons']):
            errors.append(
                'The icons property must be an object (got %s)'
                % json.dumps(manifest['icons']))
        else:
            for key in manifest['icons']:
                if not is_string(manifest['icons'][key]):
                    errors.append(
                        'The icons[%r] property must be a string (got %s)'
                        % (key, json.dumps(manifest['icons'][key])))
                else:
                    try:
                        int(key)
                    except (ValueError, TypeError):
                        errors.append(
                            'The icons[%r] property should be a numeric pixel size'
                            % key)
                if manifest['icons'][key] == "":
                    errors.append(
                        'The icons[%r] property is empty' % key)

    if 'installs_allowed_from' in manifest:
        if not isinstance(manifest['installs_allowed_from'], (list, tuple)):
            errors.append(
                'The installs_allowed_from property must be a list (got %s)'
                % json.dumps(manifest['installs_allowed_from']))
        else:
            for index, item in enumerate(manifest['installs_allowed_from']):
                if not is_string(item):
                    errors.append(
                        'installs_allowed_from[%s] must be a string (got %s)'
                        % (index, json.dumps(item)))
                elif not is_origin_match(item):
                    errors.append(
                        'installs_allowed_from[%s] (%s) is not a proper host match string'
                        % (index, json.dumps(item)))
    if 'launch_path' in manifest:
        if not is_string(manifest['launch_path']):
            errors.append(
                'launch_path property must be a string (got %s)'
                % json.dumps(manifest['launch_path']))
        elif not is_path(manifest['launch_path']):
            errors.append(
                'launch_path property is not a proper path (got %s)'
                % json.dumps(manifest['launch_path']))
    if 'name' in manifest:
        if not is_string(manifest['name']):
            errors.append(
                'name property must be a string (got %s)'
                % json.dumps(manifest['name']))
        elif not manifest['name']:
            errors.append(
                'name property must not be empty')
        elif len(manifest['name']) >= 128:
            errors.append(
                'name property can only be 127 characters long (got %s characters)'
                % len(manifest['name']))
    else:
        errors.append(
            'The name property is required and was not provided')
    if 'version' in manifest and not is_string(manifest['version']):
        errors.append(
            'The version property must be a string (got %s)'
            % json.dumps(manifest['version']))
    if 'widget' in manifest:
        wid = manifest['widget']
        if not is_dict(wid):
            errors.append(
                'The widget property must be an object (got %s)'
                % json.dumps(wid))
        if 'path' in wid:
            if not is_string(wid['path']):
                errors.append(
                    'The widget.path property must be a string (got %s)'
                    % json.dumps(wid['path']))
            elif not is_path(wid['path']):
                errors.append(
                    'The widget.path property is not a valid path (got %s)'
                    % json.dumps(wid['path']))
        if 'width' in wid:
            if not isinstance(wid['width'], (int, float)):
                errors.append(
                    'The widget.width property must be an integer (got %s)'
                    % json.dumps(wid['width']))
            elif wid['width'] < 10 or wid['width'] > 1000:
                errors.append(
                    'The widget.width property must be [10-1000] (got %s)'
                    % json.dumps(wid['width']))
        if 'height' in wid:
            if not isinstance(wid['height'], (int, float)):
                errors.append(
                    'The widget.height property must be an integer (got %s)'
                    % json.dumps(wid['height']))
            elif wid['height'] < 10 or wid['height'] > 1000:
                errors.append(
                    'The widget.height property must be [10-1000] (got %s)'
                    % json.dumps(wid['height']))
    if 'locales' in manifest:
        if 'default_locale' not in manifest:
            errors.append(
                'The locales property requires the presence of the default_locale property')
        for lang in manifest['locales']:
            l = manifest['locales'][lang]
            # allowed: description, developer, icons, launch_path, name
            keys = set(l)
            keys -= set(['description', 'developer', 'icons', 'launch_path', 'name'])
            for key in sorted(keys):
                errors.append(
                    'Illegal property locales[%r].%s'
                    % (lang, key))
            if 'developer' in l:
                keys = set(l['developer'].keys())
                keys -= set(['email', 'url', 'name'])
                for key in sorted(keys):
                    errors.append(
                        'Illegal property locales[%r].developer.%s'
                        % (lang, key))
    keys = set(manifest.keys())
    keys -= set("""
    capabilities default_locale locales experimental description developer
    icons installs_allowed_from launch_path name version widget""".split())
    for key in sorted(keys):
        errors.append('Illegal property %s (value: %s)'
                      % (key, json.dumps(manifest[key])))
    return errors


def normalize(manifest):
    """Normalizes values in the manifest"""
    manifest = manifest.copy()
    if 'widget' in manifest:
        manifest['widget'] = manifest['widget'].copy()
    if 'icons' in manifest:
        manifest['icons'] = manifest['icons'].copy()
    if 'launch_path' in manifest:
        manifest['launch_path'] = normalize_path(manifest['launch_path'])
    if 'path' in manifest.get('widget', {}):
        manifest['widget']['path'] = normalize_path(manifest['widget']['path'])
    for key in 'width', 'height':
        if key in manifest.get('widget', {}):
            manifest['widget'][key] = int(manifest['widget'][key])
    if 'installs_allowed_from' in manifest:
        manifest['installs_allowed_from'] = [
            normalize_url(u) for u in manifest['installs_allowed_from']]
    for key in manifest.get('icons', {}):
        manifest['icons'][key] = normalize_path(manifest['icons'][key])
    if 'icons' in manifest and not manifest['icons']:
        del manifest['icons']
    return manifest


## A bunch of helpers:

def is_string(o):
    return isinstance(o, basestring)


def is_dict(o):
    return isinstance(o, dict)


def is_path(s):
    if not s.startswith('/'):
        return False
    return True


def is_origin_match(s):
    if s == '*':
        return True
    parts = urlparse.urlsplit(s)
    if parts.scheme not in ('http', 'https'):
        return False
    if parts.path and parts.path != '/':
        return False
    if parts.query or parts.fragment:
        return False
    return True


def extra_keys(d, allowed):
    extra = []
    for key in sorted(d):
        if key not in allowed:
            extra.append(key)
    return extra


## Normalizing helpers:

def normalize_path(p):
    return posixpath.normpath(p)


def normalize_url(u):
    parts = urlparse.urlsplit(u)
    if parts[0] == 'http' and parts[1].endswith(':80'):
        parts = parts[:1] + (parts[1][:-3],) + parts[2:]
    elif parts[0] == 'https' and parts[1].endswith(':443'):
        parts = parts[:1] + (parts[1][:-4],) + parts[2:]
    if not parts[2]:
        parts = parts[:2] + ('/',) + parts[3:]
    return urlparse.urlunsplit(parts)
