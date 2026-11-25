#version 330 core

// small blocks lying in the world (instanced): one cube per drop

layout (location = 0) in vec3 in_position;  // cube in [-0.5, 0.5]
layout (location = 1) in vec3 in_normal;
layout (location = 2) in vec2 in_uv;
layout (location = 3) in float in_face;     // face id as in chunk.frag (0 top, 1 bottom, 2..5 sides)
layout (location = 4) in vec4 in_place;     // center xyz, rotation around y
layout (location = 5) in vec2 in_item;      // size, block id

uniform mat4 m_proj;
uniform mat4 m_view;

out vec2 uv;
out vec3 normal;
out vec3 frag_world_pos;
flat out int face_id;
flat out int voxel_id;

void main() {
    float c = cos(in_place.w), s = sin(in_place.w);
    mat3 rot = mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c);
    vec3 world = in_place.xyz + rot * (in_position * in_item.x);
    normal = rot * in_normal;
    uv = in_uv;
    face_id = int(in_face + 0.5);
    voxel_id = int(in_item.y + 0.5);
    frag_world_pos = world;
    gl_Position = m_proj * m_view * vec4(world, 1.0);
}
