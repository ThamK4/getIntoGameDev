#include "swapchain.h"
#include "../logging/logger.h"
#include "image.h"

void Swapchain::rebuild(
    vk::Device logicalDevice,
    vk::PhysicalDevice physicalDevice,
    vk::SurfaceKHR surface,
    GLFWwindow* window) {

    Logger* logger = Logger::get_logger();
    logger->print("Recreating swapchain!");

    // wait
    logicalDevice.waitIdle();

    destroy(logicalDevice);

    // recreate
    int width, height;
    glfwGetFramebufferSize(window, &width, &height);
    build(logicalDevice, physicalDevice, surface, width, height);
}

void Swapchain::destroy(vk::Device logicalDevice) {

    while (deletionQueue.size() > 0) {
        deletionQueue.back()(logicalDevice);
        deletionQueue.pop_back();
    }

    images.clear();
    imageViews.clear();
}

void Swapchain::build(
    vk::Device logicalDevice, vk::PhysicalDevice physicalDevice, 
    vk::SurfaceKHR surface, uint32_t width, uint32_t height) {

    Logger* logger = Logger::get_logger();

    logger->set_mode(false);

    SurfaceDetails support = query_surface_support(
        physicalDevice, surface);

    format = choose_surface_format(support.formats);

    vk::PresentModeKHR presentMode = choose_present_mode(
        support.presentModes);

    extent = choose_extent(width, height, support.capabilities);

    imageCount = std::min(
        support.capabilities.maxImageCount,
        support.capabilities.minImageCount + 1
    );

    /*
    * VULKAN_HPP_CONSTEXPR SwapchainCreateInfoKHR(
    VULKAN_HPP_NAMESPACE::SwapchainCreateFlagsKHR flags_         = {},
    VULKAN_HPP_NAMESPACE::SurfaceKHR              surface_       = {},
    uint32_t                                      minImageCount_ = {},
    VULKAN_HPP_NAMESPACE::Format                  imageFormat_   = VULKAN_HPP_NAMESPACE::Format::eUndefined,
    VULKAN_HPP_NAMESPACE::ColorSpaceKHR   imageColorSpace_  = VULKAN_HPP_NAMESPACE::ColorSpaceKHR::eSrgbNonlinear,
    VULKAN_HPP_NAMESPACE::Extent2D        imageExtent_      = {},
    uint32_t                              imageArrayLayers_ = {},
    VULKAN_HPP_NAMESPACE::ImageUsageFlags imageUsage_       = {},
    VULKAN_HPP_NAMESPACE::SharingMode     imageSharingMode_ = VULKAN_HPP_NAMESPACE::SharingMode::eExclusive,
    uint32_t                              queueFamilyIndexCount_ = {},
    const uint32_t *                      pQueueFamilyIndices_   = {},
    VULKAN_HPP_NAMESPACE::SurfaceTransformFlagBitsKHR preTransform_ =
    VULKAN_HPP_NAMESPACE::SurfaceTransformFlagBitsKHR::eIdentity,
    VULKAN_HPP_NAMESPACE::CompositeAlphaFlagBitsKHR compositeAlpha_ =
    VULKAN_HPP_NAMESPACE::CompositeAlphaFlagBitsKHR::eOpaque,
    VULKAN_HPP_NAMESPACE::PresentModeKHR presentMode_  = VULKAN_HPP_NAMESPACE::PresentModeKHR::eImmediate,
    VULKAN_HPP_NAMESPACE::Bool32         clipped_      = {},
    VULKAN_HPP_NAMESPACE::SwapchainKHR   oldSwapchain_ = {} ) VULKAN_HPP_NOEXCEPT
    */
    vk::SwapchainCreateInfoKHR createInfo = 
    vk::SwapchainCreateInfoKHR(vk::SwapchainCreateFlagsKHR(), 
        surface, imageCount, format.format, format.colorSpace,
        extent, 1, vk::ImageUsageFlagBits::eColorAttachment | vk::ImageUsageFlagBits::eTransferDst);

    createInfo.preTransform = support.capabilities.currentTransform;
    createInfo.presentMode = presentMode;
    createInfo.clipped = VK_TRUE;

    createInfo.oldSwapchain = vk::SwapchainKHR(nullptr);

    auto result = logicalDevice.createSwapchainKHR(createInfo);
    if (result.result == vk::Result::eSuccess) {
        chain = result.value;

        deletionQueue.push_back([this, logger](vk::Device device){
            logger->print("Destroyed swapchain");
            device.destroySwapchainKHR(chain);
        });
    }
    else {
        logger->print("failed to create swap chain!");
    }

    uint32_t imageCount;
    logicalDevice.getSwapchainImagesKHR(chain, &imageCount, NULL);
    images.resize(imageCount);
    logicalDevice.getSwapchainImagesKHR(chain, &imageCount, images.data);
    
    for (uint32_t i = 0; i < images.size; ++i) {
        vk::ImageView imageView = create_image_view(logicalDevice, images[i], format.format);
        imageViews.push_back(imageView);
        VkImageView imageViewHandle = imageView;
        deletionQueue.push_back([imageViewHandle](vk::Device device) {
            vkDestroyImageView(device, imageViewHandle, nullptr);
        });
    }

    logger->set_mode(true);

    outdated = false;
}

SurfaceDetails Swapchain::query_surface_support(
        vk::PhysicalDevice physicalDevice, 
        vk::SurfaceKHR surface) {

    Logger* logger = Logger::get_logger();
	
    SurfaceDetails support;
    support.capabilities = physicalDevice
        .getSurfaceCapabilitiesKHR(surface).value;
	logger->print(support.capabilities);
	
    uint32_t count;
    physicalDevice.getSurfaceFormatsKHR(surface, &count, NULL);
    support.formats.resize(count);
    physicalDevice.getSurfaceFormatsKHR(surface, &count, support.formats.data);
    logger->print(support.formats);

    physicalDevice.getSurfacePresentModesKHR(surface, &count, NULL);
    support.presentModes.resize(count);
    physicalDevice.getSurfacePresentModesKHR(surface, &count, support.presentModes.data);
    logger->print("Supported Present Modes:");
    logger->print(support.presentModes);
	
	return support;
}

vk::SurfaceFormatKHR Swapchain::choose_surface_format(
    DynamicArray<vk::SurfaceFormatKHR> formats) {

    for (size_t i = 0; i < formats.size; ++i) {
        vk::SurfaceFormatKHR format = formats[i];
        if (format.format == vk::Format::eB8G8R8A8Unorm
            && format.colorSpace == vk::ColorSpaceKHR::eSrgbNonlinear) {
            return format;
        }
    }

    return formats[0];
}

vk::PresentModeKHR Swapchain::choose_present_mode(
    DynamicArray<vk::PresentModeKHR> presentModes) {
    
    for (size_t i = 0; i < presentModes.size; ++i) {
        vk::PresentModeKHR presentMode = presentModes[i];
        if (presentMode == vk::PresentModeKHR::eImmediate) {
            return presentMode;
        }
    }

    return vk::PresentModeKHR::eFifo;
}

vk::Extent2D Swapchain::choose_extent(
    uint32_t width, uint32_t height, 
    vk::SurfaceCapabilitiesKHR capabilities) {

    if (capabilities.currentExtent.width != UINT32_MAX) {
        return capabilities.currentExtent;
    }
    else {
        vk::Extent2D extent = { width, height };

        extent.width = std::min(
            capabilities.maxImageExtent.width, 
            std::max(capabilities.minImageExtent.width, extent.width)
        );

        extent.height = std::min(
            capabilities.maxImageExtent.height,
            std::max(capabilities.minImageExtent.height, extent.height)
        );

        return extent;
    }
}
