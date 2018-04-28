#!/bin/sh
source /etc/profile
SERVICE_PATH=/root/run
SERVICE_NAME={{service_name}}.{{service_postfix}}
INIT_SERVICE=/etc/init.d/{{service_name}}
export LANG=en_US.UTF-8
export LC_CTYPE=en_US.UTF-8
chmod 755 $SERVICE_PATH/$SERVICE_NAME
IPADDR=`ifconfig eth0|grep Bcast|awk -F: '{print $2}'|awk -F "" '{print $1}'`
export MAVEN_OTPS="-Xms512m -Xmx2048m -Xss20m"
start() {
  echo "Starting $SERVICE_NAME"
  $INIT_SERVICE start --spring.profiles.active={{env_name}} --eureka.instance.hostname=$IPADDR
}
stop() {
  local PID
  echo "Stopping $SERVICE_NAME"
  PID=$(ps -ef|grep $SERVICE_NAME|grep -v grep|awk '{print $2}')
  kill -9 $PID
  echo "$PID killed"
}
restart() {
  echo "Restarting $SERVICE_NAME"
   $INIT_SERVICE restart --spring.profiles.active={{env_name}} --eureka.instance.hostname=$IPADDR
}
status() {
   $INIT_SERVICE status --spring.profiles.active={{env_name}} --eureka.instance.hostname=$IPADDR
}
usage() {
  echo "Usage: $(basename $0) start|status|stop|restart"
}
case "$1" in
  start)
 start
  ;;
  stop)
 stop
  ;;
  restart)
 restart
  ;;
  status)
 status
  ;;
  *)
 usage && exit 1
    ;;
esac    
