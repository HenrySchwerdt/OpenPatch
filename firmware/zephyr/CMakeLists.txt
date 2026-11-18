# OpenPatch pod firmware (nRF Connect SDK v3.4.x / Zephyr 4.x).
# EXPERIMENTAL DIY DEVICE - NOT A MEDICAL DEVICE.
#
# Use firmware/scripts/build.sh (sets up the toolchain environment, signing key and sysbuild).
#   Rev A board : west build --sysbuild -b openpatch_reva/nrf52840 firmware/zephyr
#   Dev kit     : west build --sysbuild -b nrf52840dk/nrf52840 firmware/zephyr -- -DEXTRA_CONF_FILE=dev.conf
cmake_minimum_required(VERSION 3.20.0)

# Custom board lives in ./boards (HWMv2: boards/<vendor>/<board>/board.yml).
list(APPEND BOARD_ROOT ${CMAKE_CURRENT_LIST_DIR})

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(openpatch)

set(OP_CORE_DIR ${CMAKE_CURRENT_LIST_DIR}/../core)
file(GLOB OP_CORE_SRC CONFIGURE_DEPENDS ${OP_CORE_DIR}/src/*.c)
file(GLOB OP_APP_SRC CONFIGURE_DEPENDS ${CMAKE_CURRENT_LIST_DIR}/src/*.c)

target_sources(app PRIVATE ${OP_APP_SRC} ${OP_CORE_SRC})
target_include_directories(app PRIVATE ${OP_CORE_DIR}/include src)
# The portable core is warning-clean at -Wconversion on the host; keep it that way here.
set_source_files_properties(${OP_CORE_SRC} PROPERTIES COMPILE_OPTIONS "-Wconversion;-Wsign-conversion")
