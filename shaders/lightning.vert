#version 330 core

#include "env.glsl"

// lightning bolt: ribbons along the segments, turned towards the camera
layout (location = 0) in vec3 in_position;
layout (location = 1) in vec3 in_direction;   // direction of the segment
layout (location = 2) in float in_side;       // -1 / 1: edge of the ribbon
layout (location = 3) in float in_width;
layout (location = 4) in float in_intensity;

uniform mat4 m_proj;
uniform mat4 m_view;

out float edge;
out float intensity;

void main() {
    vec3 to_cam = normalize(camera.xyz - in_position);
    vec3 side = normalize(cross(in_direction, to_cam));
    float dist = length(camera.xyz - in_position);
    float width = in_width * max(1.0, dist * 0.004);  // stays visible far away
    vec3 p = in_position + side * in_side * width;
    edge = in_side;
    intensity = in_intensity;
    gl_Position = m_proj * m_view * vec4(p, 1.0);
}
