# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# CMake delegates compilation to the same pinned CLI and validators.
include_guard(GLOBAL)
get_filename_component(_LEFONY_SDK_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
get_filename_component(_LEFONY_BUNDLE_ROOT "${_LEFONY_SDK_ROOT}/../.." ABSOLUTE)
if(WIN32)
  set(_LEFONY_EXECUTABLE_NAME "lefony-sdk.exe")
else()
  set(_LEFONY_EXECUTABLE_NAME "lefony-sdk")
endif()
if(EXISTS "${_LEFONY_BUNDLE_ROOT}/${_LEFONY_EXECUTABLE_NAME}" AND EXISTS "${_LEFONY_SDK_ROOT}/../runtime/firmware.elf")
  set(_LEFONY_CLI "${_LEFONY_BUNDLE_ROOT}/${_LEFONY_EXECUTABLE_NAME}")
else()
  find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)
  set(_LEFONY_CLI "${Python3_EXECUTABLE}" "${_LEFONY_SDK_ROOT}/tools/cli.py")
endif()
function(lefony_add_app target)
  add_custom_target(${target} ALL
    COMMAND ${_LEFONY_CLI}
            --project "${CMAKE_CURRENT_SOURCE_DIR}" package
            --profile "$<IF:$<CONFIG:Debug>,debug,release>"
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    COMMENT "Building the pinned native Lefony app"
    VERBATIM)
endfunction()
