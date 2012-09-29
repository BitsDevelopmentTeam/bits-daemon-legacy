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

#include <list>
#include <string>
#include <boost/asio.hpp>
#include <boost/thread.hpp>
#include <boost/shared_ptr.hpp>

#ifndef PUSH_SERVER
#define PUSH_SERVER

/**
 * Server to handle push clients and send them status updates
 */
class PushServer
{
public:
	/**
	 * \param port Start the push server on a given port
	 * \param maxClients Maximum number of accepted clients
	 * (the default value is safe and does not require to tweak ulimit)
	 */  
	PushServer(int port, int maxClients=500);

	/**
	 * \param message message to send to connected clients
	 */
	void send(const std::string& message);

	/**
	 * \param message this message is sent as soon as a new WebSocket
	 * is started. It is meant as a way to send status information
	 * to clients when they connect
	 */
	void welcomeMessage(const std::string& message);

	/**
	 * Destructor
	 */
	~PushServer();

private:
	PushServer(const PushServer&);
	PushServer& operator= (const PushServer&);

	/**
	 * An instance of this class keeps track of a client
	 */
	class Client
	{
	public:
		/// Maximum size to prevent DoS attacks, passed to asio::streambuf
		/// Works in different ways depending on whether the socket is at the
		/// HTTP header stage, or WebSocket stage:
		/// - HTTP headers are received with async_read_until("\r\n\r\n")
		///   so if the HTTP header exceeds this size onClientData() is
		///   called with an error code and this causes the socket to be closed
		/// - WebSocket data is read with async_read_some(maxSize) so data is
		///   simply split in chunks of maxSize maximum and no error occurs
		static const int maxSize=1024;

		Client(boost::shared_ptr<boost::asio::ip::tcp::socket> sock)
				: sock(sock), readData(new boost::asio::streambuf(maxSize)),
				  pendingWrites(0), connectionUpgraded(false),
				  lastPacket(false) {}

		boost::shared_ptr<boost::asio::ip::tcp::socket> sock;
		boost::shared_ptr<boost::asio::streambuf> readData;
		int pendingWrites;
		bool connectionUpgraded;
		bool lastPacket;
	};

	/**
	 * \param data input text string
	 * \return data, encoded in a WebSocket text frame
	 */
	static std::string packAsTextFrame(const std::string& data);

	/**
	 * Send data to a client and close the connection
	 * \param it packet is sent to this client
	 * \param data data to send
	 */
	void lastPacket(std::list<Client>::iterator it,
			boost::shared_ptr<std::string> data);

	/**
	 * The only background thread spawned has this function as main loop
	 */
	void serverMainLoop();

	/**
	 * Calling send() causes this to be called in the background thread
	 * \param data data to send to clients
	 */
	void onSend(boost::shared_ptr<std::string> data);

	/**
	 * Calling welcomeMessage() causes this to be called in the background thread
	 * \param dataWs data encoded in a WebSocket text frame
	 * \param dataHttp data encoded in an HTTP reply
	 */
	void onWelcomeMessage(boost::shared_ptr<std::string> dataWs,
			boost::shared_ptr<std::string> dataHttp);

	/**
	 * Destroying the object causes this to be called in the background thread
	 */
	void onClose();

	/**
	 * A new client connecting causes this to be called in the background thread
	 * \param ec if errors occurred
	 * \param sock socket with the client
	 */
	void onConnect(const boost::system::error_code& ec,
			boost::shared_ptr<boost::asio::ip::tcp::socket> sock);

	/**
	 * A client sending data causes this to be called in the background thread
	 * \param ec if errors occurred
	 * \param bytesReceived number of bytes received
	 * \param it client id
	 */
	void onClientData(const boost::system::error_code& ec, int bytesReceived,
			std::list<Client>::iterator it);

	/**
	 * A completed write causes this to be called in the background thread
	 * \param ec if errors occurred
	 * \param data data being sent. It is a trick for the reference counting
	 * mechanism: since a reference exists till this function is called, the
	 * buffer is not deallocated until the packet is sent (desired behaviour)
	 * \param it client id
	 */
	void onWriteCompleted(const boost::system::error_code& ec,
			boost::shared_ptr<std::string> data,
			std::list<Client>::iterator it);

	boost::asio::io_service io;
	boost::asio::ip::tcp::endpoint ep;
	boost::asio::ip::tcp::acceptor server;
	std::list<Client> clients;
	boost::thread serverThread;
	std::string welcomeWs;
	boost::shared_ptr<std::string> welcomeHttp;
	const int maxClients;
};

#endif //PUSH_SERVER
