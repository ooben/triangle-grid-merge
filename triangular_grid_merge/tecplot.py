"""
Module provides interaction with tecplot format.
"""
from .node import Node
from .face import Face
from .edge import Edge
from .grid import Grid
from .zone import Zone
from .node_algorithms import n_square, dichotomy_1_sided, dichotomy_2_sided


def print_tecplot(grid, filename, merge=False):
    """
    Write grid containing multiple zones to the file.

    :param grid: Grid object.
    :param filename: file to write in.
    :param merge: (bool) whether to merge grid.
    Use ids of the nodes in grid.Nodes instead of zone.Nodes.
    And the ids of faces from grid.Faces instead of zone.Faces.
    I.e. continuing numbering through the grid.
    """
    print_tecplot_header(filename)

    if merge:
        print_merged_grid(grid, filename)
    else:
        print_zones(grid, filename)


def print_zones(grid, filename):
    """
    Print grid's zones to the filename.

    Warning! if you use this function to add zones
    to the existing tecplot file already containing zones
    then the numeration of zone titles should be handled manually.

    :param grid: Grid object.
    :param filename: file to plot zones in.
    """
    for i, z in enumerate(grid.Zones):
        print_zone_header(filename, 'ZONE {}'.format(i + 1), z.Nodes, z.Faces)

        print_variables(filename, z.Nodes)

        print_connectivity_list(filename, z.Nodes, z.Faces)


def print_merged_grid(grid, filename):
    """
    Merge all zones and print the grid as single zone.

    Use continuous numbering of nodes and faces through the grid
     instead of their position zone-wise.

    :param grid: Grid object.
    :param filename: file to write in.
    """
    assert len(grid.Zones) > 1, '\nGrid is not multizone.\n'

    print_zone_header(filename, 'ZONE 1', grid.Nodes, grid.Faces)

    print_variables(filename, grid.Nodes)

    print_connectivity_list(filename, grid.Nodes, grid.Faces)


def read_tecplot(grid, filename, algorithm='dichotomy_2_sided'):
    """
    Read tecplot file.

    :param grid: Grid object.
    :param filename: file to read from.
    :param algorithm: algorithm to compare nodes' coordinates when merging zones.

    `n_square` given a node searches for it by trivial element by element search.

    `dichotomy_2_sided` given a node uses dichotomy to locate a node with equal x-coordinate and
    continues to compare y-coordinate of neighbor elements with equal x-coordinates in two directions.

    `dichotomy_1_sided` given a node uses dichotomy to locate a node with equal x-coordinate and which stays first
    of all nodes with equal x-coordinate when the algorithm continues to compare y-coordinate of neighbor elements
    with equal x-coordinates in one directions (to the right).
    """
    if algorithm not in ['n_square', 'dichotomy_1_sided', 'dichotomy_2_sided']:
        raise Exception('Wrong name for algorithm')

    file_with_grid = open(filename, 'r')

    lines = file_with_grid.readlines()

    faces_count = list()
    indexes = list()

    # Find and remember all ELEMENTS words in the file.
    # They design a start of zone.
    for i, line in enumerate(lines):
        if line.find('ELEMENTS =') != -1:
            faces_count.append(number_of_faces(line))

            # +3 is the correction to start from the line
            # where the variables start.
            indexes.append(i + 3)

    # List of lists of nodes for each zone.
    nodes = list()
    # List of lists of faces for each zone.
    faces = list()

    # Extract each zone from certain lines using indexes of lines
    # obtained earlier.
    for f, i in zip(faces_count, indexes):
        # Create a zone.
        z = Zone()
        grid.Zones.append(z)

        # Return nodes and faces for the zone
        # by parcing the file.
        parces_nodes, parces_faces = parce_nodes_and_faces(lines[i: i + 2 + f])
        nodes.append(parces_nodes)
        faces.append(parces_faces)

        z.Nodes = parces_nodes
        z.Faces = parces_faces

    set_nodes(grid, nodes, algorithm)

    for f, n in zip(faces, nodes):
        set_faces(grid, n, f)
        grid.Faces += f

    # Init new elements' ids.
    grid.init_ids()


def set_nodes(grid, nodes, algorithm):
    """
    Fill grid.Nodes list with unique nodes from each zone.

    :param grid: Grid object.
    :param nodes: list of lists of nodes for each zone.
    :param algorithm: algorithm to merge nodes from multiple zones.
    """
    for n in nodes:
        if algorithm == 'n_square':
            n_square(grid, n)
        if algorithm == 'dichotomy_1_sided':
            dichotomy_1_sided(grid, n)
        if algorithm == 'dichotomy_2_sided':
            dichotomy_2_sided(grid, n)


def set_faces(grid, nodes, faces):
    """
    Link faces and nodes according to the connectivity list.

    1 2 3  -> Face 1
    2 3 4  -> Face 2

    Also, edges are created and linked basing on their presence in grid.Edge.

    :param grid: Grid object.
    :param nodes: list : nodes to link.
    :param faces: list : faces to link.
    """
    for f in faces:
        n1 = nodes[f.nodes_ids[0] - 1]
        n2 = nodes[f.nodes_ids[1] - 1]
        n3 = nodes[f.nodes_ids[2] - 1]

        # Link face and nodes.
        Grid.link_face_and_node(f, n1)
        Grid.link_face_and_node(f, n2)
        Grid.link_face_and_node(f, n3)

        # Link faces, nodes and edges.
        e = grid.is_edge_present(n1, n2)
        if e is None:
            e = Edge()
            grid.link_face_and_edge(f, e)
            grid.link_node_and_edge(n1, e)
            grid.link_node_and_edge(n2, e)
            grid.Edges.append(e)
        else:
            grid.link_face_and_edge(f, e)

        e = grid.is_edge_present(n2, n3)
        if e is None:
            e = Edge()
            grid.link_face_and_edge(f, e)
            grid.link_node_and_edge(n2, e)
            grid.link_node_and_edge(n3, e)
            grid.Edges.append(e)
        else:
            grid.link_face_and_edge(f, e)

        e = grid.is_edge_present(n3, n1)
        if e is None:
            e = Edge()
            grid.link_face_and_edge(f, e)
            grid.link_node_and_edge(n3, e)
            grid.link_node_and_edge(n1, e)
            grid.Edges.append(e)
        else:
            grid.link_face_and_edge(f, e)


def parce_nodes_and_faces(lines):
    """
    Parce node and faces from tecplot file.

    Creates list of nodes and list of faces.
    Set the x, y coordinates of nodes.

    Add list of nodes' ids to each face.

    :param lines: tecplot lines representing the
    value and connectivity lists.

    :return: tuple (list, list): nodes and faces for a zone.
    """
    # Read all nodes of zone 1.
    # x coords.
    xs = map(float, lines[0].split(' ')[:-1])
    # y coords.
    ys = map(float, lines[1].split(' ')[:-1])

    # Nodes of zone 1.
    nodes = list()

    # Initialize node array for zone 1.
    for x, y in zip(xs, ys):
        n = Node()
        n.x = x
        n.y = y
        nodes.append(n)

    del xs
    del ys

    faces = list()

    for line in lines[2:]:
        f = Face()
        ids = line.split(' ')[:-1]
        ids = list(map(int, ids))
        f.nodes_ids = ids
        faces.append(f)

    return nodes, faces


def number_of_zones(file):
    """
    Count the number of times the word ZONE occurs in the file.

    :param file: file to read.
    :return: number of zones.
    """
    return ' '.join(file).count('ZONE T')


def number_of_nodes(line):
    """
    Extract the number of nodes from te line.

    :param line: line with the word NODES
    :return: int number of nodes.
    """
    return int(line[line.find('NODES =') + 7: len(line)])


def number_of_faces(line):
    """
    Extract the number of nodes from te line.

    :param line: line with the word NODES
    :return: int number of nodes.
    """
    return int(line[line.find('ELEMENTS =') + 10: len(line)])


def print_tecplot_header(filename):
    """
    Write tecplot header containing the information
    about Title and number of variables.

    :param filename: file to write in.
    """
    with open(filename, 'w') as f:
        f.write('TITLE = "GRID"\n')
        f.write('VARIABLES = "X", "Y"\n')


def print_zone_header(filename, zone_name, nodes, faces):
    """
    Write information about zone into the file.

    :param filename: file to write in.
    :param zone_name: name of the zone.
    :param nodes: nodes.
    :param faces: faces.
    """
    with open(filename, 'a+') as f:
        f.write('ZONE T = "{}"\n'.format(zone_name))
        f.write('NODES = {}\n'.format((len(nodes))))
        f.write('ELEMENTS = {}\n'.format((len(faces))))
        f.write('DATAPACKING = BLOCK\n')
        f.write('ZONETYPE = FETRIANGLE\n')


def print_variables(filename, nodes):
    """
    Write variables values in tecplot file.

    :param filename: file to write in.
    :param nodes: nodes containing values.
    """
    with open(filename, 'a+') as f:
        # Variables' values.
        for node in nodes:
            f.write(str(node.x) + ' ')

        f.write('\n')

        for node in nodes:
            f.write(str(node.y) + ' ')
        f.write('\n')


def print_connectivity_list(filename, nodes, faces):
    """
    Write tecplot connectivity list.

    :param filename: file to write in.
    :param faces: faces with nodes.
    """
    with open(filename, 'a+') as f:
        # Connectivity list.
        for face in faces:
            for node in face.nodes:
                f.write(str(nodes.index(node) + 1) + ' ')
            f.write('\n')
