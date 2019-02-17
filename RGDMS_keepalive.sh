#!/bin/bash

#this script will create a file in /tmp every minute and if RGDMS does not delete it by the next time this script runs, it will kill and restart the app
# location of heartbeat file: /tmp/RGDMS.heartbeat
# location of pid file: /tmp/RGDMS.pid
# location of previous read heartbeat: /tmp/RGDMS.previousheartbeat

#if first run, create previousheartbeat file
if [ ! -f /tmp/RGDMS.previousheartbeat ]; then
  echo 0 > /tmp/RGDMS.previousheartbeat
fi

if [[ `cat /tmp/RGDMS.heartbeat` > `cat /tmp/RGDMS.previousheartbeat` ]];then
  #RGDMS is still active, check back later...
  cp /tmp/RGDMS.heartbeat /tmp/RGDMS.previousheartbeat
else
  #RGDMS seems to be hung up, kill it and let it respawn...
  current_time=`eval date +%Y-%m-%d":"%H:%M`
  echo "RGDMS hung up at $current_time, killing pid " `cat /tmp/RGDMS.pid` >> /tmp/RGDMS_keepalive.log
  sudo kill `cat /tmp/RGDMS.pid`
fi

