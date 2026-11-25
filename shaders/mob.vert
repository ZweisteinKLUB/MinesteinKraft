#version 330 core

layout (location = 0) in vec3 in_position;
layout (location = 1) in vec3 in_normal;
layout (location = 2) in vec4 in_color;    // rgb + emissive flag
layout (location = 3) in vec4 in_joints;
layout (location = 4) in vec4 in_weights;

const int MAX_BONES = 32;

uniform mat4 m_proj;
uniform mat4 m_view;
uniform mat4 m_model;
uniform mat4 u_bones[MAX_BONES];

out vec3 color;
out float emissive;
out vec3 normal;
out vec3 frag_world_pos;

void main() {
    mat4 skin = in_weights.x * u_bones[int(in_joints.x)]
              + in_weights.y * u_bones[int(in_joints.y)]
              + in_weights.z * u_bones[int(in_joints.z)]
              + in_weights.w * u_bones[int(in_joints.w)];
    vec4 world = m_model * skin * vec4(in_position, 1.0);
    normal = normalize(mat3(m_model) * mat3(skin) * in_normal);
    color = in_color.rgb;
    emissive = in_color.a;
    frag_world_pos = world.xyz;
    gl_Position = m_proj * m_view * world;
}
