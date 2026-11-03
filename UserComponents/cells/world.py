"""Montagem do Bairro Arterial: colisao exportada do Blender + arte + navegacao."""
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, BoxShape, TriangleMeshShape
from .visuals import Block
from .layout import MAP_DATA
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


def build_district(game):
    floor = game.CreateItem()
    floor.name = 'Bairro Arterial collision'
    floor.AddComponent(PhysicsBody3D(TriangleMeshShape(MAP_DATA['vertices'], MAP_DATA['indices']),
                                   body_type=BodyType.STATIC))
    game.CreateItem().AddComponent(DistrictScenery())
    return Navigator(game.physics_world)
