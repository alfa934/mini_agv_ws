cmake_minimum_required(VERSION 3.8)
project(mini_agv_hardware)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

# Add custom library
add_library(serialib STATIC src/serialib.cpp)
target_include_directories(serialib PUBLIC include)

# Executables
add_executable(serial_node src/serial_node.cpp)
ament_target_dependencies(serial_node rclcpp std_msgs geometry_msgs)
target_link_libraries(serial_node serialib)

# Install
install(TARGETS serial_node DESTINATION lib/${PROJECT_NAME})

ament_package()
