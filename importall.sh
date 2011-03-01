#!/bin/sh

if [ -z "$1" ] ; then
  BASE="http://localhost:8080"
else
  BASE="$1"
fi

for SITE in \
    http://hakim.se/experiments/html5/sketch/manifest.webapp \
    http://raptjs.com/manifest.webapp \
    http://regamez.com/madtanks/mozilla.webapp \
    http://shazow.net/linerage/gameon/manifest.json \
    http://sinuousgame.com/manifest.webapp \
    http://stillalivejs.t4ils.com/play/manifest.webapp \
    http://tubagames.net/barfight_manifest.php \
    http://websnooker.com/manifest.webapp \
    http://www.davesgalaxy.com/site_media/mozilla.manifest \
    http://www.harmmade.com/vectorracer/manifest.webapp \
    http://www.limejs.com/roundball.webapp \
    http://www.limejs.com/zlizer.webapp \
    http://www.paulbrunt.co.uk/steamcube/manifest.webapp \
    http://www.phoboslab.org/ztype/manifest.webapp \
    ; do
  echo "Importing $SITE"
  curl -X POST --header 'Accept: text/plain' $BASE/add?manifest_url="$SITE"
  echo
done
