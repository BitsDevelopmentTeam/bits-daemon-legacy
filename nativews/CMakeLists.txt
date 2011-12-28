
cmake_minimum_required(VERSION 2.6)
project(PushServer)

set(CMAKE_BUILD_TYPE Release)
# This adds -DDEBUG_MODE to redirect serial port to console
add_definitions(-DDEBUG_MODE)

find_package(SWIG REQUIRED)
include(${SWIG_USE_FILE})

find_package(PythonLibs)
include_directories(${PYTHON_INCLUDE_PATH})

include_directories(${CMAKE_CURRENT_SOURCE_DIR})

set(CMAKE_SWIG_FLAGS "")

set_source_files_properties(push_server.i PROPERTIES CPLUSPLUS ON)
swig_add_module(ws python push_server.i push_server.cpp base64.cpp sha1.cpp)
swig_link_libraries(ws ${PYTHON_LIBRARIES})

## Link libraries
set(BOOST_LIBS thread regex system)
find_package(Boost COMPONENTS ${BOOST_LIBS} REQUIRED)
swig_link_libraries(ws ${Boost_LIBRARIES})
find_package(Threads REQUIRED)
swig_link_libraries(ws ${CMAKE_THREAD_LIBS_INIT})
