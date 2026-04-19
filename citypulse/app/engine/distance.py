import math


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_distance_matrix(clients, depot):
    nodes = [depot] + clients
    n = len(nodes)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine(nodes[i]["latitude"], nodes[i]["longitude"],
                          nodes[j]["latitude"], nodes[j]["longitude"])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def euclidean_distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def build_euclidean_matrix(clients, depot):
    nodes = [depot] + clients
    n = len(nodes)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = euclidean_distance(nodes[i]["latitude"], nodes[i]["longitude"],
                                   nodes[j]["latitude"], nodes[j]["longitude"])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix
