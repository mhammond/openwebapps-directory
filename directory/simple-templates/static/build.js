$(function () {
  $('input,textarea').live('change keyup', function () {
    // FIXME: use timeout here
    updateManifest();
  });
  updateManifest();
  var iconCounter = 0;
  $('#add-icon').click(function () {
    var newName = 'new-' + iconCounter++;
    var row = $('<tr class="icon-row"><td>Icon:<a href="#" class="remove">x</a></td><td>URL: <input type="text" name="icon_url_'
                + newName + '"><br>'
                + 'Size: <input type="text" name="icon_size_'
                + newName + '"></td></tr>');
    $('#add-icon').parents('tr').before(row);
  });
  $('.icon-row .remove').live('click', function () {
    var el = $(this).parents('tr.icon-row');
    el.remove();
    return false;
  });
});

function buildManifest(values) {
  var obj = {};
  obj.name = values.name;
  if (values.description) {
    obj.description = values.description;
  }
  if (values.launch_path && values.launch_path != '/') {
    obj.launch_path = values.launch_path;
  }
  if (values.icons) {
    obj.icons = {};
    for (var group in values.icons) {
      obj.icons[values.icons[group].size] = values.icons[group].url;
    }
  }
  if (values.developer_name) {
    obj.developer = obj.developer || {};
    obj.developer.name = values.developer_name;
  }
  if (values.developer_url) {
    obj.developer = obj.developer || {};
    obj.developer.url = values.developer_url;
  }
  if (values.developer_email) {
    obj.developer = obj.developer || {};
    obj.developer.email = values.developer_email;
  }
  if (values.keywords) {
    obj.experimental = obj.experimental || {};
    obj.experimental.keywords = values.keywords;
  }
  if (values.widget_path) {
    obj.widget = {path: values.widget_path};
    if (values.widget_height) {
      obj.widget.height = parseInt(values.widget_height, 10);
    }
    if (values.widget_width) {
      obj.widget.width = parseInt(values.widget_width, 10);
    }
  }
  return obj;
}

function updateManifest() {
  var manifest = buildManifest(getValuesFromForm($('#generation-form')));
  $('#manifest').val(JSON.stringify(manifest, null, "  "));
}

function getValuesFromForm(form) {
  form = $(form);
  var values = {};
  values.url = getField('url', form);
  values.name = getField('name', form);
  var copyNames = ['description', 'launch_path', 'developer_name',
                   'developer_url', 'developer_email',
                   'widget_path', 'widget_width', 'widget_height'];
  for (var i=0; i<copyNames.length; i++) {
    var val = getField(copyNames[i], form);
    if (val) {
      values[copyNames[i]] = val;
    }
  }
  var keywords = getField('keywords', form);
  if (keywords) {
    keywords = keywords.split(',');
    values.keywords = [];
    for (var i=0; i<keywords.length; i++) {
      var k = keywords[i];
      k = k.replace(/^\s*/, '');
      k = k.replace(/\s*$/, '');
      if (k) {
        values.keywords.push(k);
      }
    }
  }
  var names = getFieldNames(form);
  var icons = {};
  var anyIcons = false;
  for (var i=0; i<names.length; i++) {
    var name = names[i];
    var match = /^icon_([^_]+)_(.*)$/.exec(name);
    if (match) {
      anyIcons = true;
      var t = match[1];
      var group = match[2];
      if (! (group in icons)) {
          icons[group] = {};
      }
      icons[group][t] = getField(name, form);
    }
  }
  if (anyIcons) {
    values.icons = icons;
  }
  return values;
}

function getField(name, form) {
  var el = $('[name='+name+']', form);
  if (el.length) {
    return el.val();
  } else {
    return null;
  }
}

function getFieldNames(form) {
  var names = [];
  $('input,textarea', form).each(function () {
    var name = this.getAttribute('name');
    if (name) {
      names.push(name);
    }
  });
  return names;
}
