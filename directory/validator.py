"""Validates the manifest files"""
from directory.util import json

__all__ = ['content_type', 'validate']

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
        elif len(manifest['description']) > 1024:
            errors.append(
                'description property can only be 1024 characters long (got %s characters)'
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
                    % json.dumps(dev['name']))
            extra = extra_keys(dev, ['name', 'url'])
            if extra:
                errors.append(
                    'The developer object has unknown keys: %s'
                    ', '.join(extra))
    if 'icons' in manifest:
        if not is_dict(manifest['icons']):
            errors.append(
                'The icons property must be an object (got %s)'
                % json.dumps(manifest['icons']))
        else:
            for key in manifest['icons']:
                if not is_string(manifest['icons'][key]):
                    errors.append(
                        'The icons.%s property must be a string (got %s)'
                        % json.dumps(manifest['icons'][key]))
                elif not manifest['icons'][key]:
                    errors.append(
                        'The icon.%s property is empty')
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
        if 'path' not in wid:
            errors.append(
                'The widget.path property is missing')
        elif not is_string(wid['path']):
            errors.append(
                'The widget.path property must be a string (got %s)'
                % json.dumps(wid['path']))
        elif not is_path(wid['path']):
            errors.append(
                'The widget.path property is not a valid path (got %s)'
                % json.dumps(wid['path']))
        if 'width' in wid:
            if not isinstance(wid['width'], int):
                errors.append(
                    'The widget.width property must be an integer (got %s)'
                    % json.dumps(wid['width']))
            elif 10 > wid['width'] > 1000:
                errors.append(
                    'The widget.width property must be [10-1000]')
        if 'height' in wid:
            if not isinstance(wid['height'], int):
                errors.append(
                    'The widget.height property must be an integer (got %s)'
                    % json.dumps(wid['height']))
            elif 10 > wid['height'] > 1000:
                errors.append(
                    'The widget.height property must be [10-1000]')

    return errors


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
    ## FIXME: do better origin check
    return True


def extra_keys(d, allowed):
    extra = []
    for key in sorted(d):
        if key not in allowed:
            extra.append(key)
    return extra
