cmake_minimum_required(VERSION 3.20)
project(openpatch_core C)

# OpenPatch portable core + host test suite.
# EXPERIMENTAL DIY DEVICE - NOT A MEDICAL DEVICE.
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

option(OP_COVERAGE "Build with LLVM source-based coverage" OFF)
option(OP_SANITIZE "Build tests with ASan+UBSan" OFF)

file(GLOB OP_CORE_SRC CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/core/src/*.c)
add_library(openpatch_core STATIC ${OP_CORE_SRC})
target_include_directories(openpatch_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/core/include)
target_compile_options(openpatch_core PRIVATE -Wall -Wextra -Wshadow -Wconversion -Wsign-conversion -Werror)

set(OP_FLAGS "")
if(OP_COVERAGE)
  list(APPEND OP_FLAGS -fprofile-instr-generate -fcoverage-mapping -O0)
endif()
if(OP_SANITIZE)
  list(APPEND OP_FLAGS -fsanitize=address,undefined -fno-sanitize-recover=undefined -g)
endif()
if(OP_FLAGS)
  target_compile_options(openpatch_core PRIVATE ${OP_FLAGS})
endif()

enable_testing()
file(GLOB OP_TEST_SRC CONFIGURE_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/tests/*.c)
add_executable(op_tests ${OP_TEST_SRC})
target_link_libraries(op_tests PRIVATE openpatch_core)
target_include_directories(op_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(op_tests PRIVATE -Wall -Wextra -Wshadow ${OP_FLAGS})
if(OP_FLAGS)
  target_link_options(op_tests PRIVATE ${OP_FLAGS})
endif()
add_test(NAME op_tests COMMAND op_tests)
