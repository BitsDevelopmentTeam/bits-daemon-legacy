/***************************************************************************
 *   Copyright (C) 2011, 2012 by Terraneo Federico                         *
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful,       *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU General Public License for more details.                          *
 *                                                                         *
 *   As a special exception, if other files instantiate templates or use   *
 *   macros or inline functions from this file, or you compile this file   *
 *   and link it with other works to produce a work based on this file,    *
 *   this file does not by itself cause the resulting work to be covered   *
 *   by the GNU General Public License. However the source code for this   *
 *   file must still be made available in accordance with the GNU General  *
 *   Public License. This exception does not invalidate any other reasons  *
 *   why a work based on this file might be covered by the GNU General     *
 *   Public License.                                                       *
 *                                                                         *
 *   You should have received a copy of the GNU General Public License     *
 *   along with this program; if not, see <http://www.gnu.org/licenses/>   *
 ***************************************************************************/

#include <sstream>
#include <boost/regex.hpp>
#include <boost/lexical_cast.hpp>
#include "base64.h"
#include "sha1.h"
#include "push_server.h"

using namespace std;
using namespace boost;

//
// class ShutdownException
//

class ShutdownException {};

//
// class PushServer
//

PushServer::PushServer(int port, int maxClients)
		: ep(asio::ip::tcp::v4(),port), server(io,ep),
		  serverThread(bind(&PushServer::serverMainLoop,this)),
		  maxClients(maxClients) {}

void PushServer::send(const string& message)
{
	shared_ptr<string> data(new string(packAsTextFrame(message)));
	io.post(bind(&PushServer::onSend,this,data));
}

void PushServer::welcomeMessage(const string& message)
{
	string encodedWs;
	if(message.empty()==false) encodedWs=packAsTextFrame(message);
	shared_ptr<string> dataWs(new string(encodedWs));
	static const string http200=
		"HTTP/1.1 200 OK\r\n"
		"Vary: Accept-Encoding\r\n"
		"Connection: Close\r\n"
		"Content-Type: text/json; charset=utf-8\r\n"
		"Content-Length: "
	;
	shared_ptr<string> dataHttp(new string(http200+
		lexical_cast<string>(message.length())+"\r\n\r\n"+message));
	io.post(bind(&PushServer::onWelcomeMessage,this,dataWs,dataHttp));
}

PushServer::~PushServer()
{
	io.post(bind(&PushServer::onClose,this));
	serverThread.join();
}

string PushServer::packAsTextFrame(const string& data)
{
	const int len=data.length();
	assert(len<65536); //Unimplemented for larger sizes
	string result;
	stringstream ss;
	if(len<=125)
	{
		result.reserve(len+2);
		ss<<"\x81"<<static_cast<char>(len & 0xff);
	} else {
		result.reserve(len+4);
		ss<<"\x81\x7e"<<static_cast<char>((len>>8) & 0xff)
		  <<static_cast<char>(len & 0xff);
	}
	result=ss.str();
	result+=data;
	return result;
}

void PushServer::lastPacket(list<Client>::iterator it, shared_ptr<string> data)
{
	if(it->lastPacket) return;
	it->lastPacket=true;
	async_write(*it->sock,asio::buffer(*data),
					bind(&PushServer::onWriteCompleted,this,
					asio::placeholders::error,data,it));
}

void PushServer::serverMainLoop()
{
	shared_ptr<asio::ip::tcp::socket> newClient(new asio::ip::tcp::socket(io));
	server.async_accept(*newClient,bind(&PushServer::onConnect,this,
						asio::placeholders::error,newClient));
	try {
		io.run();
	} catch(ShutdownException&) {}
}

void PushServer::onSend(shared_ptr<string> data)
{
	for(list<Client>::iterator it=clients.begin();it!=clients.end();++it)
	{
		if(it->connectionUpgraded==false) continue;
		async_write(*it->sock,asio::buffer(*data),
					bind(&PushServer::onWriteCompleted,this,
					asio::placeholders::error,data,it));
	}
}

void PushServer::onWelcomeMessage(shared_ptr<string> dataWs,
		shared_ptr<string> dataHttp)
{
	welcomeWs=*dataWs;
	welcomeHttp=dataHttp;
}

void PushServer::onClose()
{
	server.close();
	clients.clear();
	throw ShutdownException();
}

void PushServer::onConnect(const boost::system::error_code& ec,
		boost::shared_ptr<boost::asio::ip::tcp::socket> sock)
{
	// Note: tests done on linux show that if the number of active
	// socket file descriptors exceeds the result of "ulimit -n"
	// the number of sockets beyond that hang, and the server suddenly
	// goes to 100% CPU utilization. This condition is recovered as
	// clients are killed. Anyway, to prevent the DoS potential of
	// a 100% CPU consumption, sockets beyond maxClients are dropped.
	if(!ec && clients.size()<=maxClients)
	{
		clients.push_front(Client(sock));
		list<Client>::iterator it=clients.begin();
		async_read_until(*it->sock,*it->readData,"\r\n\r\n",
				bind(&PushServer::onClientData,this,
				asio::placeholders::error,
				asio::placeholders::bytes_transferred,it));
	}

	//Get ready to accept the next one
	shared_ptr<asio::ip::tcp::socket> newClient(new asio::ip::tcp::socket(io));
	server.async_accept(*newClient,bind(&PushServer::onConnect,this,
						asio::placeholders::error,newClient));
}

void PushServer::onClientData(const boost::system::error_code& ec,
		int bytesReceived, list<Client>::iterator it)
{
	if(ec)
	{
		clients.erase(it); //Errors while reading? close the socket
		return;
	}

	if(it->connectionUpgraded)
	{
		//See example in documentation of boost::asio::streambuf
		it->readData->commit(bytesReceived);

		clients.erase(it); //Unexpected data? close the socket
		return;
	}

	istream is(it->readData.get());
	bool h0=false; //H0: header containing "GET /data.json HTTP/1.1"
	static const regex h0r("GET /data\\.json HTTP/1\\.[01]\r?");
	bool h1=false; //H1: header containing "Upgrade: websocket"
	static const regex h1r("Upgrade\\: websocket\r?");
	bool h2=false; //H2: header containing "Connection: Upgrade"
	static const regex h2r("Connection\\:.*Upgrade.*");
	bool h3=false; //H3: empty line marking the "\r\n\r\n" (end of HTTP req.)
	static const regex challengeMatch("Sec-WebSocket-Key\\: .*");
	static const regex challengeReplace("(Sec-WebSocket-Key\\: )|(\r$)");
	string challenge;
	string line;
	while(getline(is,line))
	{
		if(regex_match(line,h0r))      { h0=true; continue; }
		if(regex_match(line,h1r))      { h1=true; continue; }
		if(regex_match(line,h2r))      { h2=true; continue; }
		if(line.empty() || line=="\r") { h3=true; continue; }
		if(regex_match(line,challengeMatch))
			challenge=regex_replace(line,challengeReplace,"",format_all);
	}
	if(h3==false ||
	   (h0==false && (h1==false || h2==false || challenge.empty())) ||
	   (h0==true && (h1==true || h2==true || challenge.empty()==false)))
	{
		static const string error404=
			"HTTP/1.1 404 Not Found\r\n"
			"Vary: Accept-Encoding\r\n"
			"Connection: Close\r\n"
			"Content-Length: 87\r\n"
			"Content-Type: text/html; charset=iso-8859-1\r\n\r\n"
			"<html><head><title>404 Not Found</title></head><body>\n"
			"<h1>Not Found</h1></body></html>\n"
		;
		lastPacket(it,shared_ptr<string>(new string(error404)));
		return;
	}
	if(h0)
	{
		//Serve the valid HTTP GET
		lastPacket(it,welcomeHttp);
		return;
	}

	static const string magic="258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
	static const string header=
		"HTTP/1.1 101 Switching Protocols\r\n"
		"Upgrade: websocket\r\n"
		"Connection: Upgrade\r\n"
		"Sec-WebSocket-Accept: "
	;
	unsigned char hash[sha1size];
	sha1binary(challenge+magic,hash);
	shared_ptr<string> data(
		new string(header+base64_encode(hash,sha1size)+"\r\n\r\n"+welcomeWs));
	async_write(*it->sock,asio::buffer(*data),
				bind(&PushServer::onWriteCompleted,this,
				asio::placeholders::error,data,it));

	it->connectionUpgraded=true;
	it->sock->async_read_some(it->readData->prepare(Client::maxSize),
				bind(&PushServer::onClientData,this,
				asio::placeholders::error,
				asio::placeholders::bytes_transferred,it));
}

void PushServer::onWriteCompleted(const system::error_code& ec,
		shared_ptr<string> data, list<Client>::iterator it)
{
	if(!ec && !it->lastPacket) return;
	clients.erase(it); //Close the socket
}
