#version 330 core

#include "env.glsl"

layout (location = 0) in uint packed_data;

int x, y , z;
int ao_id;
int flip_id;

uniform mat4 m_proj;
uniform mat4 m_view;
uniform mat4 m_model;

flat out int voxel_id;
flat out int face_id;

out vec2 uv;
out float ao;
out vec3 frag_world_pos;

const float ao_values[4] = float[4](0.22, 0.45, 0.72, 1.0);
const int LEAVES_ID = 6;

const vec2 uv_coords[4] = vec2[4](
    vec2(0, 0), vec2(0, 1),
    vec2(1, 0), vec2(1, 1)
);

const int uv_indices[24] = int[24](
    1, 0, 2, 1, 2, 3,  // tex coords indices for vertices if an even Face
    3, 0, 2, 3, 1, 0,   // odd face
    3, 1, 0, 3, 0, 2,  // even flipped face
    1, 2, 3, 1, 0, 2   // odd flipped face
);


void unpack(uint packed_data) {
    // a, b, c, d, e, f, g = x, y, z, voxel_id, face_id, ao_id, flip_id
    uint b_bit = 6u, c_bit = 6u, d_bit = 8u, e_bit = 3u, f_bit = 2u, g_bit = 1u;
    uint b_mask = 63u, c_mask = 63u, d_mask = 255u, e_mask = 7u, f_mask = 3u, g_mask = 1u;
    //
    uint fg_bit = f_bit + g_bit;
    uint efg_bit = e_bit + fg_bit;
    uint defg_bit = d_bit + efg_bit;
    uint cdefg_bit = c_bit + defg_bit;
    uint bcdefg_bit = b_bit + cdefg_bit;
    // unpacking vertex data
    x = int(packed_data >> bcdefg_bit);
    y = int((packed_data >> cdefg_bit) & b_mask);
    z = int((packed_data >> defg_bit) & c_mask);
    //
    voxel_id = int((packed_data >> efg_bit) & d_mask);
    face_id = int((packed_data >> fg_bit) & e_mask);
    ao_id = int((packed_data >> g_bit) & f_mask);
    flip_id = int(packed_data & g_mask);
}


void main() {
    unpack(packed_data);

    vec3 in_position = vec3(x, y, z);
    int uv_index = gl_VertexID % 6 + ((face_id & 1) + flip_id * 2) * 6;

    uv = uv_coords[uv_indices[uv_index]];

    ao = ao_values[ao_id];

    vec3 world = (m_model * vec4(in_position, 1.0)).xyz;
    if (voxel_id == LEAVES_ID) {
        // foliage sways in the wind (a function of the position only: shared corners stay joined)
        float t = zenith.w;
        float gust = 0.03 + 0.09 * wind.z;
        float phase = dot(world, vec3(0.31, 0.17, 0.23));
        world.xz += wind.xy * gust * (sin(t * 1.7 + phase) * 0.6 + sin(t * 3.1 + phase * 1.7) * 0.4);
        world.y += gust * 0.4 * sin(t * 2.3 + phase * 1.3);
    }
    frag_world_pos = world;

    gl_Position = m_proj * m_view * vec4(world, 1.0);
}