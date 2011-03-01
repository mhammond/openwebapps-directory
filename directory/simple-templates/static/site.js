window.addEventListener('load', function () {
  var buttons = document.getElementsByTagName('button');
  var buttonsByOrigin = {};
  for (var i=0; i<buttons.length; i++) {
    var button = buttons[i];
    if (button.className.search(/install-button/) == -1) {
      continue;
    }
    var appOrigin = button.getAttribute('apporigin');
    addClickHandler(button);
    buttonsByOrigin[appOrigin] = button;
  }
  navigator.apps.getInstalledBy(function (repo) {
    for (var i=0; i<repo.length; i++) {
      if (repo[i].origin in buttonsByOrigin) {
        var button = buttonsByOrigin[repo[i].origin];
        button.disabled = true;
        button.innerHTML = 'already installed';
      }
    }
  }); // there's an onerror callback, but we don't care about
      // errors
}, false);

function addClickHandler(button) {
  var manifestURL = button.getAttribute('appurl');
  var appOrigin = button.getAttribute('apporigin');
  button.addEventListener('click', function (e) {
    console.log('installing...', manifestURL);
    navigator.apps.install({
      url: manifestURL,
      onsuccess: function () {
        button.disabled = true;
        button.innerHTML = 'Installed!';
      },
      onerror: function (reason) {
        log('Install failed:', reason);
        button.parentNode.insertBefore(
          createErrorDiv(reason.code + ': ' + reason.message),
          button.nextSibling);
        button.className += ' error';
      }
    });
  }, false);
}

function log() {
  if (typeof console != 'undefined' && console.log) {
    console.log.apply(console, arguments);
  }
}

function createErrorDiv(message) {
  var node = document.createElement('div');
  node.className = 'error';
  node.appendChild(document.createTextNode(message));
  return node;
}
