#!/bin/sh

while true
do
  status_code=200
  response_status=`curl -o /dev/null -s -w  %{http_code} http://192.168.11.55:8181/dologin`
  if [[ $status_code -eq $response_status ]]
  then
    echo "FRS is running ok!"
    break
  else
    sleep 2
    echo "wait to start!"
    continue
  fi
done
