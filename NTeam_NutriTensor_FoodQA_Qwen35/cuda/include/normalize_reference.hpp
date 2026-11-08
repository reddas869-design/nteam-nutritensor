#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace nteam {

// This profiling exercise is independent of the model's own image processor.
// It deliberately performs no resizing, tiling, tokenization or vision inference.
struct Normalization {
    std::array<float, 3> mean{0.485f, 0.456f, 0.406f};
    std::array<float, 3> standard_deviation{0.229f, 0.224f, 0.225f};

    void validate() const {
        for (std::size_t channel = 0; channel < 3; ++channel) {
            if (!std::isfinite(mean[channel]) ||
                !std::isfinite(standard_deviation[channel]) ||
                standard_deviation[channel] <= 0.0f) {
                throw std::invalid_argument("Normalization constants must be finite; standard deviation must be positive");
            }
        }
    }
};

inline std::size_t image_elements(int width, int height) {
    if (width < 1 || height < 1 || width > 8192 || height > 8192) {
        throw std::invalid_argument("Image dimensions must be in [1, 8192]");
    }
    const auto pixels = static_cast<std::size_t>(width) * static_cast<std::size_t>(height);
    if (pixels > std::numeric_limits<std::size_t>::max() / (3 * sizeof(float))) {
        throw std::overflow_error("Image size overflows address space");
    }
    return pixels * 3;
}

inline void normalize_reference(
    const std::uint8_t* input,
    float* output,
    int width,
    int height,
    const Normalization& constants
) {
    const auto elements = image_elements(width, height);
    if (input == nullptr || output == nullptr) {
        throw std::invalid_argument("Image buffers must not be null");
    }
    constants.validate();
    const auto pixels = elements / 3;
    for (std::size_t pixel = 0; pixel < pixels; ++pixel) {
        for (std::size_t channel = 0; channel < 3; ++channel) {
            const float value = static_cast<float>(input[pixel * 3 + channel]) / 255.0f;
            output[channel * pixels + pixel] =
                (value - constants.mean[channel]) / constants.standard_deviation[channel];
        }
    }
}

inline float maximum_error(const float* expected, const float* actual, std::size_t elements) {
    float maximum = 0.0f;
    for (std::size_t index = 0; index < elements; ++index) {
        if (!std::isfinite(expected[index]) || !std::isfinite(actual[index])) {
            return std::numeric_limits<float>::infinity();
        }
        maximum = std::max(maximum, std::abs(expected[index] - actual[index]));
    }
    return maximum;
}

}  // namespace nteam
