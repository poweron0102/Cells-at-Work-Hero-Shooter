"""Montagem do Bairro Arterial: colisao exportada do Blender + arte + navegacao."""
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, BoxShape, TriangleMeshShape
from .visuals import Block
from . import layout
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


SCREEN_GROUP = 16  # alambrados: barram personagens (mascara -1), mas tiros (1|8) e visao (1) passam


def add_screens(game):
    """Colisao vazada do mapa (cercas de tela), num grupo que os raycasts de tiro ignoram."""
    data = layout.MAP_DATA
    if not data.get('screen_indices'):
        return None
    item = game.CreateItem()
    item.name = f'{layout.MAP_INFO.title} screens'
    return item.AddComponent(PhysicsBody3D(TriangleMeshShape(data['screen_vertices'], data['screen_indices']),
                                           body_type=BodyType.STATIC, collision_group=SCREEN_GROUP))


def build_district(game):
    floor = game.CreateItem()
    floor.name = f'{layout.MAP_INFO.title} collision'
    floor.AddComponent(PhysicsBody3D(TriangleMeshShape(layout.MAP_DATA['vertices'], layout.MAP_DATA['indices']),
                                   body_type=BodyType.STATIC))
    add_screens(game)
    game.CreateItem().AddComponent(DistrictScenery())
    return Navigator(game.physics_world)
