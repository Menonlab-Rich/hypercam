cmake_minimum_required(VERSION 3.12)
project(openeb-modules)

set(Python_ROOT_DIR, REALPATH "${CMAKE_CURRENT_SOURCE_DIR}/../../../.venv/lib/python3.12")

find_package(MetavisionHAL REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(stc_filter src/stc-filter.cpp)
pybind11_add_module(raw_cutter_py src/raw-cutter.cpp)
pybind11_add_module(event_cluster_tracker src/event-tracker-python.cpp)

target_link_libraries(raw_cutter_py PRIVATE Metavision::HAL_discovery)
