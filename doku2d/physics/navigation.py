"""Bounded grid pathfinding used by TileMap."""
from heapq import heappop, heappush
from math import sqrt


def grid_path(start, goal, walkable, *, diagonal, can_cross=None):
    if not walkable(start) or not walkable(goal):
        return []

    diagonal_cost = sqrt(2)
    straight = ((1, 0), (0, 1), (-1, 0), (0, -1))
    directions = straight + ((1, 1), (-1, 1), (-1, -1), (1, -1)) if diagonal else straight

    def estimate(point):
        dx, dy = abs(goal[0] - point[0]), abs(goal[1] - point[1])
        return dx + dy + (diagonal_cost - 2) * min(dx, dy) if diagonal else dx + dy

    first = estimate(start)
    queue = [(first, first, 0, start)]
    costs = {start: 0}
    parents = {}
    while queue:
        _, _, cost, current = heappop(queue)
        if cost != costs[current]:
            continue
        if current == goal:
            path = [goal]
            while current != start:
                current = parents[current]
                path.append(current)
            return path[::-1]

        x, y = current
        for dx, dy in directions:
            point = (x + dx, y + dy)
            if not walkable(point):
                continue
            corner = dx != 0 and dy != 0
            if corner and not (walkable((x + dx, y)) and walkable((x, y + dy))):
                continue
            if can_cross is not None and not can_cross(current, point):
                continue
            next_cost = cost + (diagonal_cost if corner else 1)
            if next_cost >= costs.get(point, float('inf')):
                continue
            costs[point] = next_cost
            parents[point] = current
            remaining = estimate(point)
            heappush(queue, (next_cost + remaining, remaining, next_cost, point))
    return []
