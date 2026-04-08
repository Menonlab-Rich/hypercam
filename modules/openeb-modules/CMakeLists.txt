cmake_minimum_required(VERSION 3.12)
project(stc-filter)

find_package(pybind11 REQUIRED)

pybind11_add_module(stc_filter src/stc-filter.cpp)
