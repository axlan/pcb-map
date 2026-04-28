# libpaho-mqtt-dev libpaho-mqttpp-dev

cmake_minimum_required(VERSION 3.14)
project(matrix_sim)
set(CMAKE_CXX_STANDARD 14)

include(FetchContent)

# SFML
FetchContent_Declare(SFML
    GIT_REPOSITORY https://github.com/SFML/SFML.git
    GIT_TAG        2.6.1
)
set(SFML_BUILD_AUDIO    OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_NETWORK  OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_DOC      OFF CACHE BOOL "" FORCE)
set(SFML_INSTALL        OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(SFML)

# ArduinoJson
FetchContent_Declare(ArduinoJson
    GIT_REPOSITORY https://github.com/bblanchon/ArduinoJson.git
    GIT_TAG        v7.4.3
)
FetchContent_MakeAvailable(ArduinoJson)

# OpenSSL
find_package(OpenSSL REQUIRED)

# Paho MQTT - installed via apt (no CMake config provided by the package)
find_library(PAHO_MQTT_C_LIB   paho-mqtt3cs  REQUIRED)
find_library(PAHO_MQTT_CPP_LIB paho-mqttpp3  REQUIRED)

# Executable
add_executable(matrix_sim
    matrix_sim.cpp
    ../src/matrix_interface.cpp
    ../src/matrix_sprite_ctrl.cpp
    mock/ESP32-HUB75-MatrixPanel-I2S-DMA.cpp
)

target_include_directories(matrix_sim PRIVATE . ../src mock)

target_link_libraries(matrix_sim PRIVATE
    ArduinoJson
    sfml-graphics
    sfml-window
    sfml-system
    ${PAHO_MQTT_CPP_LIB}
    ${PAHO_MQTT_C_LIB}
    OpenSSL::SSL
    OpenSSL::Crypto
)
