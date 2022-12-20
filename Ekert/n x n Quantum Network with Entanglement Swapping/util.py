from random import choice
from math import log
import numpy as np

def zero_runs(a):
    # Create an array that is 1 where a is 0, and pad each end with an extra 0.
    iszero = np.concatenate(([0], np.equal(a, 0).view(np.int8), [0]))
    absdiff = np.abs(np.diff(iszero))
    # Runs start and end where absdiff is 1.
    ranges = np.where(absdiff == 1)[0].reshape(-1, 2)
    return ranges

def move(a, b):
    if a < b:
        a += 1
    elif a > b:
        a -= 1
    return a

def get_random_route(network):
    network_nodes = []
    for node in network.nodes:
        network_nodes.append(eval(node))
    route = []
    A = choice(network_nodes)
    B = choice(network_nodes)
    while A == B:
        B = choice(network_nodes)
    route.append(A)
    T = [A[0], A[1]]
    while (T[0] != B[0]) or (T[1] != B[1]):
        if T[0] != B[0]:
            T[0] = move(T[0], B[0])
            route.append((T[0], T[1]))
        if T[1] != B[1]:
            T[1] = move(T[1], B[1])
            route.append((T[0], T[1]))
    return route

def binary_entropy(x):
    return -x*log(x, 2) - (1 - x)*log(1 - x, 2)

def get_neighbours(network, node, n):
    '''
    Get neighbours of each node in a n x n Grid Quantum Network
    '''
    neighbours = []
    nodes = network.nodes
    pos = eval(node.name)
    i, j = pos[0], pos[1]
    if i + 1 < n:
        neighbours.append(nodes[str((i + 1, j))])
    if i - 1 >= 0:
        neighbours.append(nodes[str((i - 1, j))])
    if j + 1 < n:
        neighbours.append(nodes[str((i, j + 1))])
    if j - 1 >= 0:
        neighbours.append(nodes[str((i, j - 1))])
    return neighbours