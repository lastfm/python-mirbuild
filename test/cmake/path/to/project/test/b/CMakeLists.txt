PROJECT(test-b)

CMAKE_MINIMUM_REQUIRED(VERSION 2.4)

INCLUDE(../../config.cmake)

INCLUDE_DIRECTORIES(../../include)

ADD_EXECUTABLE(test main ../../src/test)
