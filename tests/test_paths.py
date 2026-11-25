from paths import resource_path


def test_resources_exist():
    for name in ('chunk', 'voxel_marker', 'water', 'crack', 'ui', 'mob', 'precipitation', 'lightning'):
        assert resource_path('shaders', f'{name}.vert').is_file()
        assert resource_path('shaders', f'{name}.frag').is_file()
    for name in ('env', 'sky', 'lighting', 'waves'):
        assert resource_path('shaders', 'include', f'{name}.glsl').is_file()
    for name in ('frame.png', 'tex_array_0.png'):
        assert resource_path('assets', name).is_file()


def test_resource_path_is_absolute():
    assert resource_path('assets').is_absolute()
