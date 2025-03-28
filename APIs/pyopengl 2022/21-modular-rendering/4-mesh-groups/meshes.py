from config import *
import buffer

class MeshGroup:
    """
        A group of meshes, can be bound and drawn easily.
    """

    def __init__(self):
        """
            Initialize a new MeshGroup
        """

        self.offsets: dict[int, tuple[int]] = {}
        self.buffer = buffer.Buffer()
        self.vertices = np.array([], dtype=np.float32)
        self.indices = np.array([], dtype=np.uint32)
        self.first_vertex = 0
        self.first_index = 0
        self.VAO = glGenVertexArrays(1)

    def add_mesh_from_file(self, mesh_id: int, filename: str) -> None:
        """
            Load a mesh from a file and add it to the group.

            Parameters:

                mesh_id: id of the mesh to add. Used later for drawing.

                filename: name of the file to load.
        """

        mesh = Mesh(filename)
        vertices = mesh.vertices
        vertex_count = len(vertices)//14
        indices = mesh.indices
        index_count = len(indices)
        index_byte_offset = self.first_index * 4
        self.offsets[mesh_id] = (self.first_vertex,
                                   index_byte_offset,
                                   index_count)

        self.first_vertex += vertex_count
        self.vertices = np.append(self.vertices, vertices)

        self.first_index += index_count
        self.indices = np.append(self.indices, indices)

    def add_billboard(self, mesh_id: int, size: tuple[float]) -> None:
        """
            Create a billboard mesh and add it to the group.

            Paramters:

                mesh_id: id to the billboard to add. Used later for drawing.

                size: (width, height) of billboard.
        """

        width, height = size
        mesh = BillBoard(width, height)
        vertices = mesh.vertices
        vertex_count = len(vertices)//14
        indices = mesh.indices
        index_count = len(indices)
        index_byte_offset = self.first_index * 4
        self.offsets[mesh_id] = (self.first_vertex,
                                   index_byte_offset,
                                   index_count)

        self.first_vertex += vertex_count
        self.vertices = np.append(self.vertices, vertices)

        self.first_index += index_count
        self.indices = np.append(self.indices, indices)

        vertex_count = len(vertices)//14

    def build(self) -> None:
        """
            Build the underlying GPU resource, This action should be performed
            once, upon adding all meshes and before drawing.
        """

        vertex_count = len(self.vertices)//14

        glBindVertexArray(self.VAO)

        vertex_partition = self.buffer.add_partition(self.vertices.nbytes,
                                                     np.float32,
                                                     GL_ARRAY_BUFFER)
        index_partition = self.buffer.add_partition(self.indices.nbytes,
                                                    np.uint32,
                                                    GL_ELEMENT_ARRAY_BUFFER)
        self.buffer.build()

        self.buffer.bind(vertex_partition)
        self.buffer.blit(vertex_partition, self.vertices)

        # x, y, z, s, t, nx, ny, nz, tx, ty, tz, bx, by, bz
        offset = 0
        attribute = 0
        stride = 56
        #position
        glEnableVertexAttribArray(attribute)
        glVertexAttribPointer(attribute, 3, GL_FLOAT, GL_FALSE,
                              stride, ctypes.c_void_p(offset))
        offset += 12
        attribute += 1
        #texture
        glEnableVertexAttribArray(attribute)
        glVertexAttribPointer(attribute, 2, GL_FLOAT, GL_FALSE,
                              stride, ctypes.c_void_p(offset))
        offset += 8
        attribute += 1
        #normal
        glEnableVertexAttribArray(attribute)
        glVertexAttribPointer(attribute, 3, GL_FLOAT, GL_FALSE,
                              stride, ctypes.c_void_p(offset))
        offset += 12
        attribute += 1
        #tangent
        glEnableVertexAttribArray(attribute)
        glVertexAttribPointer(attribute, 3, GL_FLOAT, GL_FALSE,
                              stride, ctypes.c_void_p(offset))
        offset += 12
        attribute += 1
        #bitangent
        glEnableVertexAttribArray(attribute)
        glVertexAttribPointer(attribute, 3, GL_FLOAT, GL_FALSE,
                              stride, ctypes.c_void_p(offset))
        offset += 12
        attribute += 1

        self.buffer.bind(index_partition)
        self.buffer.blit(index_partition, self.indices)

        self.vertices = None
        self.indices = None

    def bind(self) -> None:
        """
            Bind the mesh group. After binding, meshes from the group
            can be drawn.
        """

        glBindVertexArray(self.VAO)

    def draw(self, mesh_id: int) -> None:
        """
            Draw a mesh.

            Parameters:

                mesh_id: id of the mesh to draw.
        """

        first_vertex, local_offset, index_count = self.offsets[mesh_id]
        index_offset = ctypes.c_void_p(local_offset\
                + self.buffer.partitions[1].offset)

        glDrawElementsBaseVertex(GL_TRIANGLES, index_count,
                                 GL_UNSIGNED_INT, index_offset, first_vertex)

    def destroy(self) -> None:
        """
            Destroy everything.
        """

        glDeleteVertexArrays(1, (self.VAO,))
        glDeleteBuffers(1,(self.buffer.device_memory,))

class Mesh:
    def __init__(self, filename: str):

        vertices, indices = self.load(filename)

        self.vertices = np.array(vertices, dtype=np.float32)
        self.indices = np.array(indices, dtype=np.uint32)

    def load(self, filename):

        #raw, unassembled data
        v = []
        vt = []
        vn = []

        #final, assembled and packed result
        vertices = []
        indices = []
        history = {}

        #open the obj file and read the data
        with open(filename,'r') as f:
            line = f.readline().replace("\n", "")
            while line:
                words = line.split(" ")
                flag = words[0]
                if flag=="v":
                    self.read_vec(v, words)
                elif flag=="vt":
                    self.read_vec(vt, words)
                elif flag=="vn":
                    self.read_vec(vn, words)
                elif flag=="f":
                    self.read_face(v, vt, vn, vertices, indices, words, history)
                line = f.readline().replace("\n", "")
        return vertices, indices

    def read_vec(self, target: list[vec], words: list[str]):
        target.append([float(x) for x in words[1:]])

    def read_face(self, 
                  v: list[list[float]], vt: list[vec], vn: list[vec], 
                  vertices: list[float], indices: list[int], words: list[str],
                  history: dict[str, int]):

        triangles_in_face = len(words) - 3

        for i in range(triangles_in_face):

            v_vt_vn_a, pos_a, tex_a, normal_a = self.unpack_corner(words[1], v, vt, vn)
            v_vt_vn_b, pos_b, tex_b, normal_b = self.unpack_corner(words[i + 2], v, vt, vn)
            v_vt_vn_c, pos_c, tex_c, normal_c = self.unpack_corner(words[i + 3], v, vt, vn)

            tangent, bitangent = self.get_btn(pos_a, tex_a, pos_b, tex_b, pos_c, tex_c)

            self.consume_corner(v_vt_vn_a, history, 
                                pos_a, tex_a, normal_a, tangent, bitangent, 
                                vertices, indices)

            self.consume_corner(v_vt_vn_b, history, 
                                pos_b, tex_b, normal_b, tangent, bitangent, 
                                vertices, indices)

            self.consume_corner(v_vt_vn_c, history, 
                                pos_c, tex_c, normal_c, tangent, bitangent, 
                                vertices, indices)

    def unpack_corner(self, v_vt_vn: str, 
                      v: list[vec], vt: list[vec], 
                      vn: list[vec]) -> tuple[str, vec, vec, vec]:

        components = [int(i) - 1 for i in v_vt_vn.split("/")]

        return v_vt_vn, v[components[0]], vt[components[1]], vn[components[2]]

    def get_btn(self, 
                pos_a: vec, tex_a: vec, 
                pos_b: vec, tex_b: vec, 
                pos_c: vec, tex_c: vec) -> tuple[vec]:

        #direction vectors
        deltaPos1 = [pos_b[i] - pos_a[i] for i in range(3)]
        deltaPos2 = [pos_c[i] - pos_a[i] for i in range(3)]
        deltaUV1 = [tex_b[i] - tex_a[i] for i in range(2)]
        deltaUV2 = [tex_c[i] - tex_a[i] for i in range(2)]
        # calculate
        den = 1 / (deltaUV1[0] * deltaUV2[1] - deltaUV2[0] * deltaUV1[1])
        tangent = []
        #tangent x
        tangent.append(den * (deltaUV2[1] * deltaPos1[0] - deltaUV1[1] * deltaPos2[0]))
        #tangent y
        tangent.append(den * (deltaUV2[1] * deltaPos1[1] - deltaUV1[1] * deltaPos2[1]))
        #tangent z
        tangent.append(den * (deltaUV2[1] * deltaPos1[2] - deltaUV1[1] * deltaPos2[2]))
        bitangent = []
        #bitangent x
        bitangent.append(den * (-deltaUV2[0] * deltaPos1[0] + deltaUV1[0] * deltaPos2[0]))
        #bitangent y
        bitangent.append(den * (-deltaUV2[0] * deltaPos1[1] + deltaUV1[0] * deltaPos2[1]))
        #bitangent z
        bitangent.append(den * (-deltaUV2[0] * deltaPos1[2] + deltaUV1[0] * deltaPos2[2]))

        return tangent, bitangent

    def consume_corner(self, v_vt_vn: str, history: dict[str, int], 
                       pos: vec, tex_coord: vec, normal: vec, 
                       tangent: vec, bitangent: vec,
                       vertices: list[float], indices: list[int]):

        if v_vt_vn in history:
            indices.append(history[v_vt_vn])
            return

        history[v_vt_vn] = len(vertices) // 14
        indices.append(history[v_vt_vn])

        for x in pos:
            vertices.append(x)
        for x in tex_coord:
            vertices.append(x)
        for x in normal:
            vertices.append(x)
        for x in tangent:
            vertices.append(x)
        for x in bitangent:
            vertices.append(x)

class BillBoard:
    def __init__(self, w: float, h: float):

        vertices = (
            0, -w/2,  h/2, 0, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0,
            0, -w/2, -h/2, 0, 1, -1, 0, 0, 0, 0, 1, 0, 1, 0,
            0,  w/2, -h/2, 1, 1, -1, 0, 0, 0, 0, 1, 0, 1, 0,
            0,  w/2,  h/2, 1, 0, -1, 0, 0, 0, 0, 1, 0, 1, 0
        )
        self.vertices = np.array(vertices, dtype=np.float32)

        self.indices = np.array((0, 1, 2, 0, 2, 3), dtype=np.uint32)

class TexturedQuad:
    def __init__(self, x: float, y: float, w: float, h: float):
        vertices = (
            x - w, y + h, 0, 1,
            x - w, y - h, 0, 0,
            x + w, y - h, 1, 0,

            x - w, y + h, 0, 1,
            x + w, y - h, 1, 0,
            x + w, y + h, 1, 1
        )
        vertices = np.array(vertices, dtype=np.float32)

        self.vertex_count = 6

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))

        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))

    def destroy(self):
        glDeleteVertexArrays(1, (self.vao,))
        glDeleteBuffers(1, (self.vbo,))

class Font:
    def __init__(self):

         #some parameters for fine tuning.
        w = 55.55 / 1000.0
        h = 63.88 / 1150.0
        heightOffset = -8.5 / 1150.0
        margin = 0.014

        """
            Letter: (left, top, width, height)
        """
        self.letterTexCoords = {
            'A': (       w, h,                          w - margin, margin - h), 'B': ( 3.0 * w, h,                          w - margin, margin - h),
            'C': ( 5.0 * w, h,                          w - margin, margin - h), 'D': ( 7.0 * w, h,                          w - margin, margin - h),
            'E': ( 9.0 * w, h,                          w - margin, margin - h), 'F': (11.0 * w, h,                          w - margin, margin - h),
            'G': (13.0 * w, h,                          w - margin, margin - h), 'H': (15.0 * w, h,                          w - margin, margin - h),
            'I': (17.0 * w, h,                          w - margin, margin - h), 'J': (       w, 3.0 * h + heightOffset,     w - margin, margin - h),
            'K': ( 3.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h), 'L': ( 5.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h),
            'M': ( 7.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h), 'N': ( 9.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h),
            'O': (11.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h), 'P': (13.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h),
            'Q': (15.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h), 'R': (17.0 * w, 3.0 * h + heightOffset,     w - margin, margin - h),
            'S': (       w, 5.0 * h + 2 * heightOffset, w - margin, margin - h), 'T': ( 3.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h),
            'U': ( 5.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h), 'V': ( 7.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h),
            'W': ( 9.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h), 'X': (11.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h),
            'Y': (13.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h), 'Z': (15.0 * w, 5.0 * h + 2 * heightOffset, w - margin, margin - h),

            'a': (       w,                     7.0 * h, w - margin, margin - h), 'b': ( 3.0 * w,                     7.0 * h, w - margin, margin - h),
            'c': ( 5.0 * w,                     7.0 * h, w - margin, margin - h), 'd': ( 7.0 * w,                     7.0 * h, w - margin, margin - h),
            'e': ( 9.0 * w,                     7.0 * h, w - margin, margin - h), 'f': (11.0 * w,                     7.0 * h, w - margin, margin - h),
            'g': (13.0 * w,                     7.0 * h, w - margin, margin - h), 'h': (15.0 * w,                     7.0 * h, w - margin, margin - h),
            'i': (17.0 * w,                     7.0 * h, w - margin, margin - h), 'j': (       w,      9.0 * h + heightOffset, w - margin, margin - h),
            'k': ( 3.0 * w,      9.0 * h + heightOffset, w - margin, margin - h), 'l': ( 5.0 * w,      9.0 * h + heightOffset, w - margin, margin - h),
            'm': ( 7.0 * w,      9.0 * h + heightOffset, w - margin, margin - h), 'n': ( 9.0 * w,      9.0 * h + heightOffset, w - margin, margin - h),
            'o': (11.0 * w,      9.0 * h + heightOffset, w - margin, margin - h), 'p': (13.0 * w,      9.0 * h + heightOffset, w - margin, margin - h),
            'q': (15.0 * w,      9.0 * h + heightOffset, w - margin, margin - h), 'r': (17.0 * w,      9.0 * h + heightOffset, w - margin, margin - h),
            's': (       w, 11.0 * h + 2 * heightOffset, w - margin, margin - h), 't': ( 3.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h),
            'u': ( 5.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h), 'v': ( 7.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h),
            'w': ( 9.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h), 'x': (11.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h),
            'y': (13.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h), 'z': (15.0 * w, 11.0 * h + 2 * heightOffset, w - margin, margin - h),

            '0': (       w, 13.0 * h, w - margin, margin - h), '1':  ( 3.0 * w,                13.0 * h, w - margin, margin - h),
            '2': ( 5.0 * w, 13.0 * h, w - margin, margin - h), '3':  ( 7.0 * w,                13.0 * h, w - margin, margin - h),
            '4': ( 9.0 * w, 13.0 * h, w - margin, margin - h), '5':  (11.0 * w,                13.0 * h, w - margin, margin - h),
            '6': (13.0 * w, 13.0 * h, w - margin, margin - h), '7':  (15.0 * w,                13.0 * h, w - margin, margin - h),
            '8': (17.0 * w, 13.0 * h, w - margin, margin - h), '9':  (       w, 15.0 * h + heightOffset, w - margin, margin - h),
            
            '.':  ( 3.0 * w,     15.0 * h + heightOffset, w - margin, margin - h), ',': ( 5.0 * w,     15.0 * h + heightOffset, w - margin, margin - h),
            ';':  ( 7.0 * w,     15.0 * h + heightOffset, w - margin, margin - h), ':': ( 9.0 * w,     15.0 * h + heightOffset, w - margin, margin - h),
            '$':  (11.0 * w,     15.0 * h + heightOffset, w - margin, margin - h), '#': (13.0 * w,     15.0 * h + heightOffset, w - margin, margin - h),
            '\'': (15.0 * w,     15.0 * h + heightOffset, w - margin, margin - h), '!': (17.0 * w,     15.0 * h + heightOffset, w - margin, margin - h),
            '"':  (       w, 17.0 * h + 2 * heightOffset, w - margin, margin - h), '/': ( 3.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h),
            '?':  ( 5.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h), '%': ( 7.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h),
            '&':  ( 9.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h), '(': (11.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h),
            ')':  (13.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h), '@': (15.0 * w, 17.0 * h + 2 * heightOffset, w - margin, margin - h)
        }

        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        with Image.open("img/Inconsolata.png", mode = "r") as img:
            image_width,image_height = img.size
            img = img.convert('RGBA')
            img_data = bytes(img.tobytes())
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,image_width,image_height,0,GL_RGBA,GL_UNSIGNED_BYTE,img_data)
        glGenerateMipmap(GL_TEXTURE_2D)

    def get_bounding_box(self, letter: str) -> tuple[float] | None:

        if letter in self.letterTexCoords:
            return self.letterTexCoords[letter]
        return None

    def use(self) -> None:
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D,self.texture)

    def destroy(self) -> None:
        glDeleteTextures(1, (self.texture,))

class TextLine:
    def __init__(self, initial_text: str, font: Font,
                 start_position: tuple[float],
                 letter_size: tuple[float]):

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.start_position = start_position
        self.letter_size = letter_size
        self.font = font
        self.build(initial_text)

    def build(self, new_text: str) -> None:

        vertices = []
        vertex_count = 0
        write_pos = 0

        margin_adjustment = 0.96

        vertices = np.zeros(24 * len(new_text), dtype = np.float32)

        for i,letter in enumerate(new_text):

            bounding_box  = self.font.get_bounding_box(letter)
            if bounding_box is None:
                continue

            #top left
            vertices[write_pos] = self.start_position[0]\
                    - self.letter_size[0]\
                    + ((2 - margin_adjustment) * i * self.letter_size[0])
            vertices[write_pos + 1] = self.start_position[1]\
                    + self.letter_size[1]
            vertices[write_pos + 2] = bounding_box[0] - bounding_box[2]
            vertices[write_pos + 3] = bounding_box[1] + bounding_box[3]
            write_pos += 4

            #top right
            vertices[write_pos] = self.start_position[0]\
                    + self.letter_size[0]\
                    + ((2 - margin_adjustment) * i * self.letter_size[0])
            vertices[write_pos + 1] = self.start_position[1]\
                    + self.letter_size[1]
            vertices[write_pos + 2] = bounding_box[0] + bounding_box[2]
            vertices[write_pos + 3] = bounding_box[1] + bounding_box[3]
            write_pos += 4
            #bottom right
            vertices[write_pos] = self.start_position[0]\
                    + self.letter_size[0]\
                    + ((2 - margin_adjustment) * i * self.letter_size[0])
            vertices[write_pos + 1] = self.start_position[1] - self.letter_size[1]
            vertices[write_pos + 2] = bounding_box[0] + bounding_box[2]
            vertices[write_pos + 3] = bounding_box[1] - bounding_box[3]
            write_pos += 4

            #bottom right
            vertices[write_pos] = self.start_position[0]\
                    + self.letter_size[0]\
                    + ((2 - margin_adjustment) * i * self.letter_size[0])
            vertices[write_pos + 1] = self.start_position[1] - self.letter_size[1]
            vertices[write_pos + 2] = bounding_box[0] + bounding_box[2]
            vertices[write_pos + 3] = bounding_box[1] - bounding_box[3]
            write_pos += 4
            #bottom left
            vertices[write_pos] = self.start_position[0]\
                    - self.letter_size[0]\
                    + ((2 - margin_adjustment) * i * self.letter_size[0])
            vertices[write_pos + 1] = self.start_position[1]\
                    - self.letter_size[1]
            vertices[write_pos + 2] = bounding_box[0] - bounding_box[2]
            vertices[write_pos + 3] = bounding_box[1] - bounding_box[3]
            write_pos += 4
            #top left
            vertices[write_pos] = self.start_position[0]\
                    - self.letter_size[0]\
                    + ((2 - margin_adjustment) * i * self.letter_size[0])
            vertices[write_pos + 1] = self.start_position[1]\
                    + self.letter_size[1]
            vertices[write_pos + 2] = bounding_box[0] - bounding_box[2]
            vertices[write_pos + 3] = bounding_box[1] + bounding_box[3]
            write_pos += 4

            vertex_count += 6

        self.vertex_count = vertex_count
        byte_size = write_pos * 4
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, byte_size, vertices, GL_STATIC_DRAW)
        offset = 0
        #position
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(offset))
        offset += 8
        #texture
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(offset))

    def destroy(self):
        glDeleteVertexArrays(1, (self.vao,))
        glDeleteBuffers(1,(self.vbo,))
