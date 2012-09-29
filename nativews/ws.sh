
HEADER="GET /ws HTTP/1.1\r\n\
Upgrade: websocket\r\n\
Connection: Upgrade\r\n\
Host: localhost:10000\r\n\
Origin: http://localhost:10000\r\n\
Sec-WebSocket-Key: ZS+MA0IUaMBc8348HHQGZw==\r\n\
Sec-WebSocket-Version: 13\r\n\
\r\n"

echo -n -e "$HEADER" | nc -4 -q 60 localhost 3389

