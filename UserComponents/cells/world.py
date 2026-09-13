"""Abrasion assembly; geometry is shared by physics, art and bot navigation."""
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, BoxShape, ConvexHullShape
from .visuals import Block
from .layout import SOLIDS, RAMPS, WIDTH, LENGTH, GATE_POSITION, GATE_SIZE
from .scenery import DistrictScenery
from .navigation import Navigator


def block(game, name, position, size, tint, solid=True):
    item = game.CreateItem()
    item.name = name
    item.transform.position = Vec3(*position)
    item.AddComponent(Block(Vec3(*size), tint))
    if solid:
        item.AddComponent(PhysicsBody3D(BoxShape(Vec3(*size)*.5), body_type=BodyType.STATIC))
    return item


def build_abrasion(game):
    floor = game.CreateItem()
    floor.name = 'Epithelium district foundation'
    floor.transform.position = Vec3(0, -.5, 0)
    floor.AddComponent(PhysicsBody3D(BoxShape(Vec3(WIDTH/2, .5, LENGTH/2)), body_type=BodyType.STATIC))
    for solid in SOLIDS:
        item = game.CreateItem()
        item.name = solid.name
        item.transform.position = Vec3(*solid.position)
        item.AddComponent(PhysicsBody3D(BoxShape(Vec3(*solid.size)*.5), body_type=BodyType.STATIC))
    for ramp in RAMPS:
        item = game.CreateItem()
        item.name = 'Public roof access ramp'
        item.AddComponent(PhysicsBody3D(ConvexHullShape(ramp.vertices), body_type=BodyType.STATIC))
    game.CreateItem().AddComponent(DistrictScenery())
    gate = game.CreateItem()
    gate.name = 'Coagulation passage'
    gate.transform.position = Vec3(*GATE_POSITION)
    body = gate.AddComponent(PhysicsBody3D(BoxShape(Vec3(*GATE_SIZE)*.5), body_type=BodyType.STATIC))
    body.enable = False
    navigator = Navigator(SOLIDS, RAMPS)
    navigator.gate = body
    return navigator, body
