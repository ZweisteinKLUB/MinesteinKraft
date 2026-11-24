import numpy as np


class BaseMesh:
    def __init__(self):
        # OpenGL context
        self.ctx = None
        # shader program
        self.program = None
        # vertex buffer data type format : "3f 3f"
        self.vbo_format = None
        # attribute names according to the format: ("in_position", "in_color")
        self.attrs: tuple[str, ...] = None
        # vertex array object (None when the mesh has no vertices)
        self.vao = None

    def get_vertex_data(self) -> np.ndarray: ...

    def get_vao(self):
        vertex_data = self.get_vertex_data()
        if vertex_data.size == 0:  # OpenGL buffers cannot be empty
            return None
        vbo = self.ctx.buffer(vertex_data)
        vao = self.ctx.vertex_array(
            self.program, [(vbo, self.vbo_format, *self.attrs)], skip_errors=True
        )
        return vao

    def render(self):
        if self.vao is not None:
            self.vao.render()
