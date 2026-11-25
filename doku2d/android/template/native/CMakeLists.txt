cmake_minimum_required(VERSION 3.22)
project(PySFMLAndroid LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

foreach(required SFML_SOURCE PYSFML_SOURCE PYTHON_PREFIX)
    if(NOT DEFINED ${required})
        message(FATAL_ERROR "Missing -D${required}")
    endif()
endforeach()

set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
set(SFML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_TEST_SUITE OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_DOC OFF CACHE BOOL "" FORCE)
set(SFML_USE_SYSTEM_DEPS OFF CACHE BOOL "" FORCE)
if(DEFINED SFML_PREFIX)
    find_package(SFML 3 REQUIRED COMPONENTS System Window Graphics Audio Network Main
        PATHS "${SFML_PREFIX}/lib/cmake/SFML"
              "${SFML_PREFIX}/lib/${ANDROID_ABI}/cmake/SFML"
              "${SFML_PREFIX}/cmake/SFML" NO_DEFAULT_PATH)
else()
    add_subdirectory("${SFML_SOURCE}" sfml)
endif()

add_library(android-python SHARED IMPORTED)
set_target_properties(android-python PROPERTIES
    IMPORTED_LOCATION "${PYTHON_PREFIX}/lib/libpython3.13.so"
    INTERFACE_INCLUDE_DIRECTORIES "${PYTHON_PREFIX}/include/python3.13")

set(STAGED_HEADERS "${CMAKE_BINARY_DIR}/pysfml-headers")
foreach(module system window graphics audio network)
    file(GLOB headers "${PYSFML_SOURCE}/src/sfml/${module}/*.h" "${PYSFML_SOURCE}/src/sfml/${module}/*.hpp")
    file(COPY ${headers} DESTINATION "${STAGED_HEADERS}/pysfml/${module}")
endforeach()

function(pysfml_module module)
    add_library(pysfml-${module} MODULE ${ARGN})
    set_target_properties(pysfml-${module} PROPERTIES
        PREFIX "" OUTPUT_NAME "${module}" SUFFIX ".so"
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/python_modules/sfml")
    target_include_directories(pysfml-${module} PRIVATE
        "${PYSFML_SOURCE}/include/Includes" "${STAGED_HEADERS}"
        "${PYSFML_SOURCE}/src/sfml/${module}")
    target_link_libraries(pysfml-${module} PRIVATE android-python SFML::System)
endfunction()

set(P "${PYSFML_SOURCE}/src/sfml")
pysfml_module(system "${P}/system/system.cpp" "${P}/system/error.cpp" "${P}/system/hacks.cpp" "${P}/system/NumericObject.cpp")
pysfml_module(window "${P}/window/window.cpp" "${P}/window/DerivableWindow.cpp")
target_link_libraries(pysfml-window PRIVATE SFML::Window)
pysfml_module(graphics "${P}/graphics/graphics.cpp" "${P}/graphics/DerivableRenderWindow.cpp" "${P}/graphics/DerivableDrawable.cpp" "${P}/graphics/NumericObject.cpp")
target_link_libraries(pysfml-graphics PRIVATE SFML::Graphics)
pysfml_module(audio "${P}/audio/audio.cpp" "${P}/audio/DerivableSoundRecorder.cpp" "${P}/audio/DerivableSoundStream.cpp")
target_link_libraries(pysfml-audio PRIVATE SFML::Audio)
pysfml_module(network "${P}/network/network.cpp")
target_link_libraries(pysfml-network PRIVATE SFML::Network)

add_library(pysfml-app SHARED main.cpp)
target_link_libraries(pysfml-app PRIVATE android-python SFML::System android log
    "-Wl,--whole-archive" SFML::Main "-Wl,--no-whole-archive")
target_link_options(pysfml-app PRIVATE "-Wl,-z,max-page-size=16384")
