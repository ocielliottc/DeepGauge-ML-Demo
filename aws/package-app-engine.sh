#!/bin/sh

if [ "`basename $PWD`" != "app-engine" ]; then
  cd app-engine 2> /dev/null
fi

if [ $? -eq 0 ]; then
  zip -x __pycache__/\* -x .e\* -x TODO -x static/img/gauge_\*.png -x static/img/live_device\*.png -r9 ../app-`date +'%Y%m%d_%H%M%S'`.zip .
else
  echo "Could not find the app-engine directory."
fi
