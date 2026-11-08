#include "normalize_reference.hpp"

#include <cuda_runtime.h>
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>

namespace {

void check_cuda(cudaError_t status, const char* operation) {
    if (status != cudaSuccess) {
        throw std::runtime_error(std::string(operation) + ": " + cudaGetErrorString(status));
    }
}

template <typename T>
class DeviceBuffer {
public:
    explicit DeviceBuffer(std::size_t count) {
        check_cuda(cudaMalloc(reinterpret_cast<void**>(&value_), count * sizeof(T)), "cudaMalloc");
    }
    ~DeviceBuffer() { if (value_) cudaFree(value_); }
    DeviceBuffer(const DeviceBuffer&) = delete;
    DeviceBuffer& operator=(const DeviceBuffer&) = delete;
    T* get() const { return value_; }
private:
    T* value_ = nullptr;
};

template <typename T>
class PinnedBuffer {
public:
    explicit PinnedBuffer(std::size_t count) {
        check_cuda(cudaMallocHost(reinterpret_cast<void**>(&value_), count * sizeof(T)), "cudaMallocHost");
    }
    ~PinnedBuffer() { if (value_) cudaFreeHost(value_); }
    PinnedBuffer(const PinnedBuffer&) = delete;
    PinnedBuffer& operator=(const PinnedBuffer&) = delete;
    T* get() const { return value_; }
private:
    T* value_ = nullptr;
};

class Stream {
public:
    Stream() { check_cuda(cudaStreamCreateWithFlags(&value_, cudaStreamNonBlocking), "cudaStreamCreate"); }
    ~Stream() { cudaStreamDestroy(value_); }
    Stream(const Stream&) = delete;
    Stream& operator=(const Stream&) = delete;
    cudaStream_t get() const { return value_; }
private:
    cudaStream_t value_{};
};

class Event {
public:
    Event() { check_cuda(cudaEventCreate(&value_), "cudaEventCreate"); }
    ~Event() { cudaEventDestroy(value_); }
    Event(const Event&) = delete;
    Event& operator=(const Event&) = delete;
    cudaEvent_t get() const { return value_; }
    void record(cudaStream_t stream) { check_cuda(cudaEventRecord(value_, stream), "cudaEventRecord"); }
    void wait() { check_cuda(cudaEventSynchronize(value_), "cudaEventSynchronize"); }
private:
    cudaEvent_t value_{};
};

struct DeviceConstants {
    float mean[3];
    float inverse_std[3];
};

// Each thread owns one output scalar. Output writes are contiguous per warp.
__global__ void normalize_scalar(
    const std::uint8_t* __restrict__ input,
    float* __restrict__ output,
    std::size_t pixels,
    DeviceConstants constants
) {
    for (std::size_t index = blockIdx.x * blockDim.x + threadIdx.x;
         index < pixels * 3;
         index += static_cast<std::size_t>(blockDim.x) * gridDim.x) {
        const auto channel = index / pixels;
        const auto pixel = index % pixels;
        const float value = static_cast<float>(input[pixel * 3 + channel]) / 255.0f;
        output[index] = (value - constants.mean[channel]) * constants.inverse_std[channel];
    }
}

// Each thread owns one RGB pixel and produces three planar output values.
__global__ void normalize_pixel(
    const std::uint8_t* __restrict__ input,
    float* __restrict__ output,
    std::size_t pixels,
    DeviceConstants constants
) {
    for (std::size_t pixel = blockIdx.x * blockDim.x + threadIdx.x;
         pixel < pixels;
         pixel += static_cast<std::size_t>(blockDim.x) * gridDim.x) {
        #pragma unroll
        for (int channel = 0; channel < 3; ++channel) {
            const float value = static_cast<float>(input[pixel * 3 + channel]) / 255.0f;
            output[channel * pixels + pixel] =
                (value - constants.mean[channel]) * constants.inverse_std[channel];
        }
    }
}

struct Options {
    int width = 1280;
    int height = 720;
    int iterations = 100;
    int block_size = 256;
    bool pixel_kernel = true;
};

int positive_integer(const char* raw) {
    std::string text(raw);
    std::size_t end = 0;
    int value = std::stoi(text, &end);
    if (end != text.size() || value < 1) throw std::invalid_argument("Expected a positive integer");
    return value;
}

Options parse(int argc, char** argv) {
    Options result;
    for (int index = 1; index < argc; index += 2) {
        if (std::string(argv[index]) == "--help") {
            std::cout << "normalize_benchmark [--width N] [--height N] [--iterations N] [--block 128|256|512] [--kernel pixel|scalar]\n";
            std::exit(0);
        }
        if (index + 1 >= argc) throw std::invalid_argument("Every option requires a value");
        const std::string flag(argv[index]);
        if (flag == "--width") result.width = positive_integer(argv[index + 1]);
        else if (flag == "--height") result.height = positive_integer(argv[index + 1]);
        else if (flag == "--iterations") result.iterations = positive_integer(argv[index + 1]);
        else if (flag == "--block") result.block_size = positive_integer(argv[index + 1]);
        else if (flag == "--kernel") {
            const std::string name(argv[index + 1]);
            if (name != "pixel" && name != "scalar") throw std::invalid_argument("Kernel must be pixel or scalar");
            result.pixel_kernel = name == "pixel";
        } else throw std::invalid_argument("Unknown option: " + flag);
    }
    nteam::image_elements(result.width, result.height);
    if (result.iterations > 10000) throw std::invalid_argument("At most 10000 iterations are permitted");
    if (result.block_size != 128 && result.block_size != 256 && result.block_size != 512) {
        throw std::invalid_argument("Block size must be 128, 256 or 512");
    }
    return result;
}

int run(const Options& options) {
    const auto elements = nteam::image_elements(options.width, options.height);
    const auto pixels = elements / 3;
    nteam::Normalization constants;
    constants.validate();
    DeviceConstants device_constants{};
    for (int channel = 0; channel < 3; ++channel) {
        device_constants.mean[channel] = constants.mean[channel];
        device_constants.inverse_std[channel] = 1.0f / constants.standard_deviation[channel];
    }
    PinnedBuffer<std::uint8_t> input(elements);
    PinnedBuffer<float> output(elements);
    DeviceBuffer<std::uint8_t> device_input(elements);
    DeviceBuffer<float> device_output(elements);
    std::vector<float> reference(elements);
    std::mt19937 random(42);
    std::uniform_int_distribution<int> distribution(0, 255);
    for (std::size_t index = 0; index < elements; ++index) input.get()[index] = distribution(random);
    const auto cpu_start = std::chrono::steady_clock::now();
    nteam::normalize_reference(input.get(), reference.data(), options.width, options.height, constants);
    const double cpu_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - cpu_start).count();
    Stream stream;
    Event start, finish;
    const auto threads = options.pixel_kernel ? pixels : elements;
    const int blocks = static_cast<int>(std::min<std::size_t>((threads + options.block_size - 1) / options.block_size, 4096));
    const auto launch = [&]() {
        if (options.pixel_kernel) {
            normalize_pixel<<<blocks, options.block_size, 0, stream.get()>>>(device_input.get(), device_output.get(), pixels, device_constants);
        } else {
            normalize_scalar<<<blocks, options.block_size, 0, stream.get()>>>(device_input.get(), device_output.get(), pixels, device_constants);
        }
        check_cuda(cudaGetLastError(), "kernel launch");
    };
    const auto copy_input = [&]() {
        check_cuda(cudaMemcpyAsync(device_input.get(), input.get(), elements, cudaMemcpyHostToDevice, stream.get()), "input copy");
    };
    const auto copy_output = [&]() {
        check_cuda(cudaMemcpyAsync(output.get(), device_output.get(), elements * sizeof(float), cudaMemcpyDeviceToHost, stream.get()), "output copy");
    };
    copy_input();
    for (int iteration = 0; iteration < 5; ++iteration) launch();
    copy_output();
    check_cuda(cudaStreamSynchronize(stream.get()), "warmup synchronization");
    const float error = nteam::maximum_error(reference.data(), output.get(), elements);
    if (error > 0.000002f) throw std::runtime_error("GPU output failed the CPU reference tolerance");
    start.record(stream.get());
    for (int iteration = 0; iteration < options.iterations; ++iteration) launch();
    finish.record(stream.get());
    finish.wait();
    float elapsed_ms = 0.0f;
    check_cuda(cudaEventElapsedTime(&elapsed_ms, start.get(), finish.get()), "kernel event timing");
    const float kernel_ms = elapsed_ms / options.iterations;
    start.record(stream.get());
    for (int iteration = 0; iteration < options.iterations; ++iteration) {
        copy_input();
        launch();
        copy_output();
    }
    finish.record(stream.get());
    finish.wait();
    check_cuda(cudaEventElapsedTime(&elapsed_ms, start.get(), finish.get()), "transfer event timing");
    const float end_to_end_ms = elapsed_ms / options.iterations;
    // Bytes read and written by the kernel, not PCIe traffic and not measured DRAM transactions.
    const double effective_gb_s = (elements * (sizeof(std::uint8_t) + sizeof(float))) / (kernel_ms * 1e6);
    std::cout << std::fixed << std::setprecision(6)
              << "{\"width\":" << options.width
              << ",\"height\":" << options.height
              << ",\"iterations\":" << options.iterations
              << ",\"block_size\":" << options.block_size
              << ",\"kernel\":\"" << (options.pixel_kernel ? "pixel" : "scalar") << "\""
              << ",\"cpu_reference_once_ms\":" << cpu_ms
              << ",\"gpu_kernel_ms\":" << kernel_ms
              << ",\"gpu_transfer_and_kernel_ms\":" << end_to_end_ms
              << ",\"effective_kernel_gb_s\":" << effective_gb_s
              << ",\"maximum_absolute_error\":" << error << "}\n";
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        return run(parse(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "Benchmark failed: " << error.what() << '\n';
        return 1;
    }
}
