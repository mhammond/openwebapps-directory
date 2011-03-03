$(function() {
  var divsByOrigin = {};

  $('div.app').each(function () {
    var div = $(this);
    var button = div.find('.button');
    var origin = div.attr('data-apporigin');
    var manifestURL = div.attr('data-appurl');
    divsByOrigin[origin] = div;
    button.click(function() {
      var callee = arguments.callee;
      button.unbind('click').removeClass("installable");
      button.html('<img src="/static/i/spinner.gif"> Installing...');
      navigator.apps.install({
        url: manifestURL,
        onsuccess: function() {
          markInstalled(div);
        },
        onerror: function(errObj) {
          button.html('<img src="/static/i/download.png"> Install');
          button.addClass('installable');
          button.click(callee);
          if (errObj.code != 'denied') {
            var error = $('<div class="error" />');
            error.text(errObj.code + ': ' + errObj.message);
            button.after(error);
          }
        }
      });
    });
  });

  navigator.apps.getInstalledBy(function (repo) {
    for (var i=0; i<repo.length; i++) {
      if (repo[i].origin in divsByOrigin) {
        var div = divsByOrigin[repo[i].origin];
        markInstalled(div);
      }
    }
    divsByOrigin = null;
  }); // there's an onerror callback, but we don't care about
      // errors

});

function markInstalled(div) {
  $(div).find(".button").addClass("installed").html("&#x2714; Installed!");
}
