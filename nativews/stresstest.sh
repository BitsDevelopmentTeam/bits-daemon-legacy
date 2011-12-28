#!/bin/sh

# Can this WebSocket server withstand the c10k shitstorm? Let's find out...

HOST='10.0.0.1'
PORT='3389'
TIMEOUT='600' # Clients die after this timeout, if not killed before
NUMCLIENTS='5000'

trap ctrl_c INT

ctrl_c() {
	echo -n 'Killing clients... '
	killall nc
	echo 'Done.'
	exit
}

HEADER="GET /ws HTTP/1.1\r\n\
Upgrade: websocket\r\n\
Connection: Upgrade\r\n\
Host: localhost:10000\r\n\
Origin: http://localhost:10000\r\n\
Sec-WebSocket-Key: ZS+MA0IUaMBc8348HHQGZw==\r\n\
Sec-WebSocket-Version: 13\r\n\
\r\n"

rm -rf stresstest_log_dir
mkdir stresstest_log_dir
echo -n "Starting $NUMCLIENTS clients... "
for i in `seq $NUMCLIENTS`; do
	echo -n "$HEADER" | nc -4 -q $TIMEOUT $HOST $PORT 1>stresstest_log_dir/$i.txt &
done
echo "Done.\nUse Ctrl-C to kill clients"
sleep $TIMEOUT
