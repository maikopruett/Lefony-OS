# SPDX-License-Identifier: CC-BY-NC-SA-4.0
cmake_minimum_required(VERSION 3.20)
project(LefonyApp LANGUAGES NONE)
set(LEFONY_SDK_ROOT "" CACHE PATH "Path to the installed SDK directory")
if(NOT EXISTS "${LEFONY_SDK_ROOT}/cmake/LefonyApp.cmake")
  message(FATAL_ERROR "Set LEFONY_SDK_ROOT to the directory containing include/, tools/ and cmake/")
endif()
include("${LEFONY_SDK_ROOT}/cmake/LefonyApp.cmake")
lefony_add_app(app)
