def wall_to_segments(walls):
    segments = []
    for wall in walls:
        verts = wall['vertices']
        n = len(verts)
        for i in range(n):
            x1, y1 = verts[i]
            x2, y2 = verts[(i + 1) % n]
            segments.append(((x1, y1), (x2, y2)))
    return segments
