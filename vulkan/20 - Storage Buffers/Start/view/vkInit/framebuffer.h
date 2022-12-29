#pragma once
#include "../../config.h"
#include "../vkUtil/frame.h"

namespace vkInit {

	struct framebufferInput {
		vk::Device device;
		vk::RenderPass renderpass;
		vk::Extent2D swapchainExtent;
	};

	void make_framebuffers(framebufferInput inputChunk, std::vector<vkUtil::SwapChainFrame>& frames) {

		std::stringstream message;

		for (int i = 0; i < frames.size(); ++i) {

			std::vector<vk::ImageView> attachments = {
				frames[i].imageView
			};

			vk::FramebufferCreateInfo framebufferInfo;
			framebufferInfo.flags = vk::FramebufferCreateFlags();
			framebufferInfo.renderPass = inputChunk.renderpass;
			framebufferInfo.attachmentCount = attachments.size();
			framebufferInfo.pAttachments = attachments.data();
			framebufferInfo.width = inputChunk.swapchainExtent.width;
			framebufferInfo.height = inputChunk.swapchainExtent.height;
			framebufferInfo.layers = 1;

			try {
				frames[i].framebuffer = inputChunk.device.createFramebuffer(framebufferInfo);

				message  << "Created framebuffer for frame " << i;
				vkLogging::Logger::get_logger()->print(message.str());
				message.str("");
			}
			catch (vk::SystemError err) {
				message << "Failed to create framebuffer for frame " << i;
				vkLogging::Logger::get_logger()->print(message.str());
				message.str("");
			}

		}
	}

}