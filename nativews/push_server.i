
// So swig can understand STL types
%include stl.i

%module ws
%{
#include "push_server.h"
%}

// Export only these parts of this class (i.e., the public interface)
class PushServer
{
public:
	PushServer(int port);
	void send(const std::string& message);
	void welcomeMessage(const std::string& message);
	~PushServer();
};
