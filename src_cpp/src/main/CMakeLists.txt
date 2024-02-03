add_executable(main)
target_sources(main
        PRIVATE src/main.cpp)

find_package(Python REQUIRED Development)
target_link_libraries(main PRIVATE Python::Python)