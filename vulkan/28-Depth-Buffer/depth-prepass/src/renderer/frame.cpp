#include "frame.h"
#include "image.h"
#include "synchronisation.h"
#include <iostream>

Frame::Frame(Swapchain& swapchain, vk::Device& logicalDevice,
	std::unordered_map<PipelineType, vk::ShaderEXT>& shaders,
	vk::DispatchLoaderDynamic& dl,
	vk::CommandBuffer commandBuffer,
	vk::Queue& queue,
	std::deque<std::function<void(vk::Device)>>& deletionQueue,
	std::unordered_map<DescriptorScope, vk::DescriptorSet>& descriptorSets,
	std::unordered_map<PipelineType, vk::PipelineLayout>& pipelineLayouts,
	VmaAllocator& allocator, StorageBuffer* vertexBuffer):
		logicalDevice(logicalDevice),
		swapchain(swapchain), shaders(shaders), dl(dl), 
		descriptorSets(descriptorSets), 
		pipelineLayouts(pipelineLayouts),
		allocator(allocator), queue(queue) {
   
	this->commandBuffer = commandBuffer;

	imageAquiredSemaphore = make_semaphore(logicalDevice, deletionQueue);
	renderFinishedSemaphore = make_semaphore(logicalDevice, deletionQueue);
	renderFinishedFence = make_fence(logicalDevice, deletionQueue);

	colorBuffer = new StorageImage(allocator, swapchain.extent, commandBuffer, 
		queue, logicalDevice, vmaDeletionQueue, deviceDeletionQueue);
	depthBuffer = make_depth_buffer(allocator, vmaDeletionQueue, swapchain.extent);

	vk::WriteDescriptorSet colorBufferWriteOp, depthBufferWriteOp, vertexBufferWriteOp;

	colorBufferWriteOp.dstSet = descriptorSets[DescriptorScope::eFrame];
	colorBufferWriteOp.dstBinding = 0;
	colorBufferWriteOp.dstArrayElement = 0;
	colorBufferWriteOp.descriptorCount = 1;
	colorBufferWriteOp.descriptorType = vk::DescriptorType::eStorageImage;
	colorBufferWriteOp.pImageInfo = &(colorBuffer->descriptor);

	depthBufferWriteOp.dstSet = descriptorSets[DescriptorScope::eFrame];
	depthBufferWriteOp.dstBinding = 1;
	depthBufferWriteOp.dstArrayElement = 0;
	depthBufferWriteOp.descriptorCount = 1;
	depthBufferWriteOp.descriptorType = vk::DescriptorType::eStorageBuffer;
	depthBufferWriteOp.pBufferInfo = &(depthBuffer.descriptor);

	vertexBufferWriteOp.dstSet = descriptorSets[DescriptorScope::eDrawCall];
	vertexBufferWriteOp.dstBinding = 0;
	vertexBufferWriteOp.dstArrayElement = 0;
	vertexBufferWriteOp.descriptorCount = 1;
	vertexBufferWriteOp.descriptorType = vk::DescriptorType::eStorageBuffer;
	vertexBufferWriteOp.pBufferInfo = &(vertexBuffer->descriptor);

	vk::WriteDescriptorSet updates[3] = { colorBufferWriteOp, depthBufferWriteOp, vertexBufferWriteOp };

	logicalDevice.updateDescriptorSets(3, updates, 0, nullptr);
}

void Frame::record_command_buffer(uint32_t imageIndex) {

	//bool smallTriangle = true;

	commandBuffer.reset();

	vk::CommandBufferBeginInfo beginInfo = {};
	commandBuffer.begin(beginInfo);

	// Transition the Storage image so the compute shader can write to it
	transition_image_layout(commandBuffer, colorBuffer->image,
		vk::ImageLayout::eUndefined, vk::ImageLayout::eGeneral,
		vk::AccessFlagBits::eNone, vk::AccessFlagBits::eMemoryWrite,
		vk::PipelineStageFlagBits::eTopOfPipe, vk::PipelineStageFlagBits::eComputeShader);

	// clear screen
	vk::ShaderStageFlagBits stage = vk::ShaderStageFlagBits::eCompute;
	commandBuffer.bindShadersEXT(1, &stage, &shaders[PipelineType::eClear], dl);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[PipelineType::eClear], 
		0, 1, &descriptorSets[DescriptorScope::eFrame], 0, nullptr);
	uint32_t workgroupCount = (swapchain.extent.width * swapchain.extent.height + 63) / 64;
	commandBuffer.dispatch(workgroupCount, 1, 1);

	// Compute barrier
	transition_image_layout(commandBuffer, colorBuffer->image,
		vk::ImageLayout::eGeneral, vk::ImageLayout::eGeneral,
		vk::AccessFlagBits::eMemoryWrite, vk::AccessFlagBits::eMemoryWrite,
		vk::PipelineStageFlagBits::eComputeShader, vk::PipelineStageFlagBits::eComputeShader);

	// draw triangles
	depth_pass();
	transition_image_layout(commandBuffer, colorBuffer->image,
		vk::ImageLayout::eGeneral, vk::ImageLayout::eGeneral,
		vk::AccessFlagBits::eMemoryWrite, vk::AccessFlagBits::eMemoryWrite,
		vk::PipelineStageFlagBits::eComputeShader, vk::PipelineStageFlagBits::eComputeShader);
	color_pass();

	// Transition storage image so it can be copied to the swapchain
	transition_image_layout(commandBuffer, colorBuffer->image,
		vk::ImageLayout::eGeneral, vk::ImageLayout::eTransferSrcOptimal,
		vk::AccessFlagBits::eMemoryWrite, vk::AccessFlagBits::eNone,
		vk::PipelineStageFlagBits::eComputeShader, vk::PipelineStageFlagBits::eNone);

	// Transitin swapchain image so we can copy to it
	transition_image_layout(commandBuffer, swapchain.images[imageIndex],
		vk::ImageLayout::eUndefined, vk::ImageLayout::eTransferDstOptimal,
		vk::AccessFlagBits::eNone, vk::AccessFlagBits::eNone,
		vk::PipelineStageFlagBits::eNone, vk::PipelineStageFlagBits::eNone);

	// Copy!
	copy_image_to_image(commandBuffer, colorBuffer->image, swapchain.images[imageIndex],
		colorBuffer->extent, swapchain.extent);

	// Transition swapchain image so it can be presented on screen
	transition_image_layout(commandBuffer, swapchain.images[imageIndex],
		vk::ImageLayout::eTransferDstOptimal, vk::ImageLayout::ePresentSrcKHR,
		vk::AccessFlagBits::eNone, vk::AccessFlagBits::eNone,
		vk::PipelineStageFlagBits::eNone, vk::PipelineStageFlagBits::eNone);

	commandBuffer.end();
}

void Frame::depth_pass() {
	vk::ShaderStageFlagBits stage = vk::ShaderStageFlagBits::eCompute;
	// Big triangle
	PipelineType pipelineType = PipelineType::eRasterizeBigDepth;
	commandBuffer.bindShadersEXT(1, &stage, &shaders[pipelineType], dl);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		0, 1, &descriptorSets[DescriptorScope::eFrame], 0, nullptr);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		1, 1, &descriptorSets[DescriptorScope::eDrawCall], 0, nullptr);
	uint32_t workgroupCountX = (static_cast<uint32_t>(800) + 7) / 8;
	uint32_t workgroupCountY = (static_cast<uint32_t>(600) + 7) / 8;
	commandBuffer.dispatch(workgroupCountX, workgroupCountY, 1);
	// Small triangles
	pipelineType = PipelineType::eRasterizeSmallDepth;
	commandBuffer.bindShadersEXT(1, &stage, &shaders[pipelineType], dl);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		0, 1, &descriptorSets[DescriptorScope::eFrame], 0, nullptr);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		1, 1, &descriptorSets[DescriptorScope::eDrawCall], 0, nullptr);
	uint32_t workgroupCount = 1;
	commandBuffer.dispatch(workgroupCount, 1, 1);
}

void Frame::color_pass() {
	vk::ShaderStageFlagBits stage = vk::ShaderStageFlagBits::eCompute;
	// Big triangle
	PipelineType pipelineType = PipelineType::eRasterizeBigColor;
	commandBuffer.bindShadersEXT(1, &stage, &shaders[pipelineType], dl);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		0, 1, &descriptorSets[DescriptorScope::eFrame], 0, nullptr);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		1, 1, &descriptorSets[DescriptorScope::eDrawCall], 0, nullptr);
	uint32_t workgroupCountX = (static_cast<uint32_t>(800) + 7) / 8;
	uint32_t workgroupCountY = (static_cast<uint32_t>(600) + 7) / 8;
	commandBuffer.dispatch(workgroupCountX, workgroupCountY, 1);
	// Small triangles
	pipelineType = PipelineType::eRasterizeSmallColor;
	commandBuffer.bindShadersEXT(1, &stage, &shaders[pipelineType], dl);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		0, 1, &descriptorSets[DescriptorScope::eFrame], 0, nullptr);
	commandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayouts[pipelineType],
		1, 1, &descriptorSets[DescriptorScope::eDrawCall], 0, nullptr);
	uint32_t workgroupCount = 1;
	commandBuffer.dispatch(workgroupCount, 1, 1);
}

void Frame::free_resources() {

	queue.waitIdle();

	while (vmaDeletionQueue.size() > 0) {
		vmaDeletionQueue.back()(allocator);
		vmaDeletionQueue.pop_back();
	}

	while (deviceDeletionQueue.size() > 0) {
		deviceDeletionQueue.back()(logicalDevice);
		deviceDeletionQueue.pop_back();
	}
}