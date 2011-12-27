/***************************************************************************
 *   Copyright (C) 2011 by Terraneo Federico                               *
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
	 */  
	PushServer(int port);

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
		Client(boost::shared_ptr<boost::asio::ip::tcp::socket> sock)
				: sock(sock), readData(new boost::asio::streambuf),
				  connectionUpgraded(false) {}

		boost::shared_ptr<boost::asio::ip::tcp::socket> sock;
		boost::shared_ptr<boost::asio::streambuf> readData;
		static const int bufferSize=128;
		char buffer[bufferSize];
		bool connectionUpgraded;
	};

	/**
	 * Transform a string into a WebSocket text frame
	 */
	static std::string packAsTextFrame(const std::string& data);

	/**
	 * The only background thread spawned has this function as main loop
	 */
	void serverMainLoop();

	/**
	 * Calling send() causes this to be called in the background thread
	 */
	void onSend(boost::shared_ptr<std::string> data);

	/**
	 * Calling welcomeMessage() causes this to be called in the background thread
	 */
	void onWelcomeMessage(boost::shared_ptr<std::string> data);

	/**
	 * Destroying the object causes this to be called in the background thread
	 */
	void onClose();

	/**
	 * A new client connecting causes this to be called in the background thread
	 */
	void onConnect(const boost::system::error_code& ec,
			boost::shared_ptr<boost::asio::ip::tcp::socket> sock);

	/**
	 * A client sending data causes this to be called in the background thread
	 */
	void onClientData(const boost::system::error_code& ec,
			std::list<Client>::iterator it);

	/**
	 * A completed write causes this to be called in the background thread
	 */
	void onWriteCompleted(const boost::system::error_code& ec,
			boost::shared_ptr<std::string> data,
			std::list<Client>::iterator it);

	boost::asio::io_service io;
	boost::asio::ip::tcp::endpoint ep;
	boost::asio::ip::tcp::acceptor server;
	std::list<Client> clients;
	boost::thread serverThread;
	std::string welcome;
};

#endif //PUSH_SERVER
