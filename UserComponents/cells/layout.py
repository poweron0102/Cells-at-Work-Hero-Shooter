"""Abrasion district: shared dimensions for collision, art and navigation (Y-up)."""
from dataclasses import dataclass

WIDTH, LENGTH = 96, 120
SPAWN_Z = 52
GATE_POSITION = (0, 1.8, 7)
GATE_SIZE = (6, 3.6, .8)


@dataclass(frozen=True)
class Solid:
    name: str
    position: tuple
    size: tuple
    tint: tuple
    facade: bool = False

    @property
    def top(self):
        return self.position[1] + self.size[1] / 2

    def contains(self, x, z, margin=0):
        return (abs(x-self.position[0]) <= self.size[0]/2 + margin
                and abs(z-self.position[2]) <= self.size[2]/2 + margin)


@dataclass(frozen=True)
class Ramp:
    x: float
    start_z: float
    end_z: float
    width: float = 5
    height: float = 4

    def surface(self, x, z):
        t = (z-self.start_z)/(self.end_z-self.start_z)
        if abs(x-self.x) <= self.width/2 and 0 <= t <= 1:
            return self.height*t
        return None

    @property
    def vertices(self):
        return [(self.x+dx, y, z) for dx in (-self.width/2, self.width/2)
                for y, z in ((-.2, self.start_z), (-.2, self.end_z), (self.height, self.end_z))]


def district_solids():
    cream, teal, pink = (238, 219, 181), (73, 130, 126), (183, 119, 114)
    solids = []
    def add(name, p, s, c, facade=False):
        solids.append(Solid(name, p, s, c, facade))
    for x in (-49, 49):
        add('Perimeter', (x, 12, 0), (2, 24, 124), pink)
    for z in (-61, 61):
        add('Perimeter', (0, 12, z), (100, 24, 2), pink)
    for x in (-14, 14):
        for z in (-22, 22):
            add('Antigen depot', (x, 2, z), (12, 4, 16), (202, 175, 139), True)
            # Short cover on roofs leaves multiple firing and landing positions.
            add('Roof ventilator', (x, 4.55, z), (3, 1.1, 2), teal)
            # Lateral galleries connect roof to the high-jump launch platform.
            side = 1 if x > 0 else -1
            add('Lateral gallery', (side*25, 3.8, z), (10, .4, 5), teal)
            add('Gallery cover', (side*25, 4.55, z+2.2), (4, 1.1, .5), cream)
    for x in (-37, 37):
        for z in (-22, 22):
            add('Receptor tower', (x, 3.5, z), (10, 7, 16), (156, 182, 161), True)
            add('Tower cover', (x, 7.65, z), (3, 1.3, 2), teal)
    add('Public skybridge', (0, 3.8, 22), (16, .4, 5), teal)
    # Nine-unit gap: slow heroes fall to the avenue; fast heroes can cross.
    for x in (-6.25, 6.25):
        add('Sprint jump landing', (x, 3.8, -22), (3.5, .4, 5), teal)
    for x, z in ((-6, -7), (6, 3), (-26, 12), (26, -12), (-27, 38), (27, -38),
                 (-6, 38), (6, -38), (-41, 0), (41, 0)):
        add('Oxygen freight', (x, .75, z), (3.5, 1.5, 3), teal)
    # Broken arch / central choke: coagulation still leaves side routes and bridge.
    for x in (-4.4, 4.4):
        add('Coagulation pier', (x, 2, 7), (2.8, 4, 2), cream)
    add('Coagulation lintel', (0, 4.2, 7), (11.6, .4, 2), pink)
    # Three protected spawn exits; offset baffles break long firing lanes.
    for side in (-1, 1):
        for x in (-31, -10, 10, 31):
            add('Spawn screen', (x, 2, side*48), (9, 4, 1.5), teal)
    return tuple(solids)


SOLIDS = district_solids()
RAMPS = tuple(Ramp(x, side*46, side*30) for x in (-14, 14) for side in (-1, 1))
