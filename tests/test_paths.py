from paths import resource_path


def test_resources_exist():
    for name in ('chunk', 'voxel_marker', 'water', 'clouds', 'crack', 'ui'):
        assert resource_path('shaders', f'{name}.vert').is_file()
        assert resource_path('shaders', f'{name}.frag').is_file()
    for name in ('frame.png', 'water.png', 'tex_array_0.png'):
        assert resource_path('assets', name).is_file()


def test_resource_path_is_absolute():
    assert resource_path('assets').is_absolute()
