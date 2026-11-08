#include "normalize_reference.hpp"

#include <iostream>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main() {
    try {
        const std::uint8_t input[] = {0, 127, 255, 255, 0, 127};
        float output[6]{};
        nteam::Normalization identity;
        identity.mean = {0.0f, 0.0f, 0.0f};
        identity.standard_deviation = {1.0f, 1.0f, 1.0f};
        nteam::normalize_reference(input, output, 2, 1, identity);
        const float expected[] = {0.0f, 1.0f, 127.0f / 255.0f, 0.0f, 1.0f, 127.0f / 255.0f};
        require(nteam::maximum_error(expected, output, 6) < 0.000001f, "HWC to CHW mapping is incorrect");
        bool invalid_dimension = false;
        try {
            nteam::image_elements(-1, 20);
        } catch (const std::invalid_argument&) {
            invalid_dimension = true;
        }
        require(invalid_dimension, "Negative dimensions were accepted");
        bool invalid_constant = false;
        identity.standard_deviation[1] = 0.0f;
        try {
            nteam::normalize_reference(input, output, 2, 1, identity);
        } catch (const std::invalid_argument&) {
            invalid_constant = true;
        }
        require(invalid_constant, "Zero standard deviation was accepted");
        output[0] = std::numeric_limits<float>::quiet_NaN();
        require(std::isinf(nteam::maximum_error(expected, output, 6)), "NaN must fail comparison");
        std::cout << "CPU reference validation passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
