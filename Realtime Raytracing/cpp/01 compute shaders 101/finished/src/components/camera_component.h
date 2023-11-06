#pragma once
#include "../config.h"

struct CameraComponent {
    glm::vec3 position;
    glm::vec3 eulers;
    glm::vec3 right;
    glm::vec3 up;
    glm::vec3 forwards;
};