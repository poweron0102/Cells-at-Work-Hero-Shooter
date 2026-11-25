"""Mapas novos (Timo, Medula Ossea, Coracao) e seus modos de objetivo.

Para cada mapa exportado: atributos do GLB, spawns e marcadores sobre chao livre, rotas das
hemacias livres, navegacao das duas bases ate todos os objetivos, bases sem linha de visao e
layout sem faces coplanares sobrepostas. Depois, as regras do treino de entrega (medula), do
batimento e do comboio (coracao) e a escolha do mapa pela sessao.
"""
import importlib
import json
import math
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'referencias'/'scripts'/'mapa'))
from simulation_support import headless_game, mount_arena, step  # noqa: E402
from EasyCells3D.Geometry import Vec3  # noqa: E402
from UserComponents.cells import layout, maps, heart  # noqa: E402
from UserComponents.cells.catalog import BALANCE, CELLS  # noqa: E402
from UserComponents.cells.rules import MatchState  # noqa: E402
from UserComponents.cells.session import connect  # noqa: E402

NEW_MAPS = ('timo', 'medula', 'coracao')
LAYOUTS = {'timo': 'timo_layout', 'medula': 'medula_layout', 'coracao': 'coracao_layout'}


class MapAssetTests(unittest.TestCase):
    def test_new_maps_are_exported_and_listed(self):
        self.assertEqual(maps.available()[:1], ['bairro'])
        for key in NEW_MAPS:
            with self.subTest(map=key):
                info = maps.info(key)
                self.assertTrue(info.exists(), info.path)
                self.assertIn(key, maps.available())
                data = json.loads((info.path/'runtime.json').read_text(encoding='utf-8'))
                self.assertEqual(data['mode'], info.mode)
                self.assertTrue((info.path/'nav.json').exists())

    def test_glb_keeps_shader_attributes_and_16_bit_batches(self):
        for key in NEW_MAPS:
            path = maps.info(key).path/maps.info(key).model_file
            with path.open('rb') as source:
                magic, version, _ = struct.unpack('<III', source.read(12))
                self.assertEqual((magic, version), (0x46546c67, 2))
                length, _ = struct.unpack('<II', source.read(8))
                data = json.loads(source.read(length))
            for mesh in data['meshes']:
                for primitive in mesh['primitives']:
                    for attribute in ('POSITION', 'NORMAL', 'COLOR_0', 'TEXCOORD_0'):
                        self.assertIn(attribute, primitive['attributes'], (key, mesh['name']))
                    count = data['accessors'][primitive['attributes']['POSITION']]['count']
                    self.assertLessEqual(count, 65535, (key, mesh['name']))

    def test_layouts_have_no_coplanar_overlapping_faces(self):
        import distrito_geo
        from check_map_overlaps import find_overlaps
        for key in NEW_MAPS:
            with self.subTest(map=key):
                geo = distrito_geo.Geo()
                importlib.import_module(LAYOUTS[key]).build(geo)
                problems = find_overlaps(geo)
                self.assertEqual(problems[:3], [], f'{len(problems)} sobreposicoes em {key}')
                self.assertEqual(geo.overlays, [])


class MapTraversalTests(unittest.TestCase):
    """Colisao exportada de cada mapa no Bullet, com a arena montada."""

    def mount(self, key):
        game = headless_game()
        net = connect(game, '127.0.0.1', 0, True, 'Mapa')
        net.start(True)
        for p in net.roster.value.values():
            p['bot'] = False
        arena = mount_arena(game, key)
        for _ in range(20):
            step(game)
        return game, arena

    def test_markers_routes_navigation_and_sight_lines(self):
        from check_rbc_routes import edge_problems
        for key in NEW_MAPS:
            with self.subTest(map=key):
                game, arena = self.mount(key)
                try:
                    world = game.physics_world
                    for slot, actor in arena.actors.items():
                        expected = layout.CELL_SPAWNS[slot % 3] if slot < 3 else layout.BACTERIA_ENTRANCE[slot % 3]
                        self.assertAlmostEqual(actor.transform.y, expected[1]+.95, delta=.2, msg=(key, slot))
                    markers = list(layout.RBC_NODES.items())+[('recon', layout.RECON)]
                    markers += [(f'colonia{i}', p) for i, p in enumerate(layout.COLONY_HINTS)]
                    for name, p in markers:
                        hit = world.raycast(Vec3(p[0], p[1]+1.5, p[2]), Vec3(0, -1, 0), 6, 1)
                        self.assertIsNotNone(hit, (key, name))
                        self.assertAlmostEqual(hit.point.y, p[1], delta=.35, msg=(key, name))
                    self.assertEqual(edge_problems(world, layout.RBC_NODES, layout.RBC_EDGES), [], key)
                    for a in layout.CELL_SPAWNS:
                        for b in layout.BACTERIA_ENTRANCE:
                            start = Vec3(a[0], a[1]+1.5, a[2])
                            delta = Vec3(b[0], b[1]+1.5, b[2])-start
                            self.assertIsNotNone(world.raycast(start, delta, delta.magnitude(), 1), key)
                    nav = arena.navigator
                    goals = [layout.RECON]+[layout.RBC_NODES[d] for doors in layout.DESTINATIONS.values() for d in doors]
                    goals += list(layout.COLONY_HINTS)+[tuple(v['pos']) for v in layout.VALVES]
                    if layout.MODE != 'training':
                        goals += [layout.ESCORT_PATH[0], layout.ESCORT_PATH[-1]]
                    for start in (layout.CELL_SPAWNS[0], layout.BACTERIA_ENTRANCE[0]):
                        for goal in goals:
                            path = nav.path(Vec3(start[0], start[1]+.95, start[2]), Vec3(goal[0], goal[1]+.95, goal[2]),
                                            1.2, 12000)
                            self.assertTrue(path, (key, start, goal))
                            self.assertLess((path[-1]-Vec3(goal[0], goal[1]+.95, goal[2])).magnitude(), 2.6,
                                            (key, goal))
                finally:
                    game.close()

    def test_chain_link_fences_stop_heroes_but_not_shots(self):
        game, arena = self.mount('timo')
        try:
            world = game.physics_world
            # Alambrado do campo em x = -30 (z 33..46): tiro (mascara 1|8) atravessa a tela.
            origin, aim = Vec3(-26, 1.4, 40), Vec3(-1, 0, 0)
            self.assertIsNone(world.raycast(origin, aim, 6, 1 | 8))
            self.assertIsNotNone(world.raycast(origin, aim, 6, 16))
            actor = arena.actors[0]
            actor.body.teleport(Vec3(-27, .95, 40))
            for _ in range(10):
                step(game)
            for _ in range(90):
                actor.controls = dict(yaw=-math.pi/2, z=1)
                step(game)
            self.assertGreater(actor.transform.x, -30, 'o heroi atravessou o alambrado')
        finally:
            game.close()


class TrainingModeTests(unittest.TestCase):
    """Medula: eritroblastos no treino de entrega."""

    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, '127.0.0.1', 0, True, 'Medula')
        self.net.start(True)
        for p in self.net.roster.value.values():
            p['bot'] = False
        self.arena = mount_arena(self.game, 'medula')
        for _ in range(10):
            step(self.game)
        self.state = self.arena.state

    def tearDown(self):
        self.game.close()

    def test_state_counts_graduations_and_seals_the_entrance(self):
        s = MatchState(mode='training', escort_total=3)
        s.tick(5.0)
        self.assertEqual(s.escort, 0)  # nada avanca com o tempo
        s.graduate()
        s.graduate()
        self.assertFalse(s.wound_closed)
        s.graduate()
        self.assertTrue(s.wound_closed)
        s.graduate()
        self.assertEqual(s.escort, 3)

    def test_arena_uses_kids_and_the_training_goal(self):
        self.assertEqual(self.arena.mode, 'training')
        self.assertEqual(self.state.escort_total, BALANCE['training_goal'])
        hem = self.arena.hemacias
        self.assertTrue(hem.kids)
        self.assertEqual(len(hem.cells), BALANCE['training_kids'])

    def test_hit_kid_drops_its_box_and_runs_home_crying(self):
        hem = self.arena.hemacias
        kid = hem.cells[0]
        kid.reset('A', hem.health)
        hem.replan(kid, hem.clock)
        kid.pos = list(layout.RBC_NODES['Tb1'])
        drops = len(self.arena.drops)
        self.arena.hit_rbc(3, 0, BALANCE['kid_health']+1)
        self.assertEqual(kid.state, 'cry')
        self.assertEqual(len(self.arena.drops), drops+1)
        self.assertEqual(self.arena.drops[-1]['amount'], BALANCE['kid_resource'])
        self.assertIsNone(hem.damage(0, 500))  # chorando nao e alvo
        self.assertEqual(kid.path[-1], 'depot')
        for _ in range(60*40):
            step(self.game, 1/60)
            if kid.state == 'inside':
                break
        self.assertEqual(kid.state, 'inside')

    def test_delivered_kid_graduates(self):
        hem = self.arena.hemacias
        kid = hem.cells[0]
        kid.reset('A', hem.health)
        kid.pos = list(layout.RBC_NODES['W3'])
        kid.state, kid.path, kid.node = 'deliver', ['A_s'], 'W3'
        before = self.state.escort
        for _ in range(60*10):
            hem.move(kid, 1/60, hem.clock)
            if kid.state == 'inside':
                break
        self.assertEqual(self.state.escort, before+1)


class HeartModeTests(unittest.TestCase):
    """Coracao: batimento, valvas, comboio e endocardite."""

    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, '127.0.0.1', 0, True, 'Coracao')
        self.net.start(True)
        for p in self.net.roster.value.values():
            p['bot'] = False
        self.arena = mount_arena(self.game, 'coracao')
        self.net.set_status('playing')
        for _ in range(10):
            step(self.game)
        self.state = self.arena.state
        for actor in self.arena.actors.values():
            if actor.team != CELLS:
                actor.health.value = 0  # nenhuma bacteria bloqueando o comboio

    def tearDown(self):
        self.game.close()

    def test_valves_alternate_with_the_heartbeat(self):
        period, systole = BALANCE['heart_period'], BALANCE['heart_systole']
        self.assertTrue(heart.beat(.1)[0])
        self.assertFalse(heart.beat(systole+.1)[0])
        self.assertTrue(heart.rhythm_open('semilunar', .1))
        self.assertFalse(heart.rhythm_open('av', .1))
        self.assertTrue(heart.rhythm_open('av', systole+.1))
        self.assertFalse(heart.rhythm_open('semilunar', period-.1))

    def test_closed_valve_body_blocks_and_opens_again(self):
        tri = self.arena.valves[0]
        body = self.arena.valve_bodies[tri['id']]
        self.state.elapsed = .5  # sistole: tricuspide fechada
        step(self.game)
        self.assertTrue(body.enable)
        world = self.game.physics_world
        hit = world.raycast(Vec3(0, 1.5, 3), Vec3(0, 0, -1), 6, 1 | 8)
        self.assertIsNotNone(hit)
        self.state.elapsed = BALANCE['heart_systole']+.5
        step(self.game)
        self.assertFalse(body.enable)

    def test_convoy_waits_at_a_closed_valve_then_crosses(self):
        tri = self.arena.valves[0]
        p = self.arena.valve_progress[tri['id']]
        self.state.escort = p-2.5
        self.state.elapsed = .05  # sistole (tricuspide fechada) por ~3 s
        self.advance(2.0)
        self.assertLessEqual(self.state.escort, p-heart.STOP_BEFORE+.01)
        self.assertEqual(self.state.blocked_valve, tri['id'])
        self.advance(BALANCE['heart_period'])
        self.assertGreater(self.state.escort, p)

    def test_colony_by_the_valve_jams_it_until_destroyed(self):
        tri = self.arena.valves[0]
        p = self.arena.valve_progress[tri['id']]
        self.state.escort = p-2.2
        self.state.resources[3] = BALANCE['colony_cost']
        x, y, z = tri['pos']
        made = self.state.add_colony(3, (x+5, 0, z+3.2))
        self.assertIsNotNone(made)
        self.advance(BALANCE['heart_period']*1.5)
        self.assertIn(tri['id'], self.state.jammed)
        self.assertLess(self.state.escort, p)
        self.assertEqual(self.state.blocked_valve, tri['id'])
        self.assertFalse(self.arena.valve_open[tri['id']])
        while self.state.colonies:
            self.state.damage_colony(made['id'], 10000)
        self.advance(BALANCE['heart_period']*1.5)
        self.assertNotIn(tri['id'], self.state.jammed)
        self.assertGreater(self.state.escort, p)

    def test_doorway_is_cleared_when_the_valve_closes(self):
        tri = self.arena.valves[0]
        actor = self.arena.actors[0]
        x, y, z = tri['pos']
        self.state.elapsed = BALANCE['heart_systole']+.5  # aberta
        step(self.game)
        actor.body.teleport(Vec3(x, y+.95, z))
        step(self.game)
        self.state.elapsed = BALANCE['heart_period']+.2  # fecha
        step(self.game)
        self.assertGreater(abs(actor.transform.z-z), .6)

    def advance(self, seconds):
        for _ in range(int(seconds*30)):
            step(self.game, 1/30)


class SessionMapTests(unittest.TestCase):
    def test_host_picks_an_available_map_in_the_lobby(self):
        game = headless_game()
        try:
            net = connect(game, '127.0.0.1', 0, True, 'Lobby')
            from UserComponents.cells import settings
            saved, original = [], settings.set_value
            settings.set_value = lambda key, value: saved.append((key, value))  # nao grava saves/config.json
            try:
                net.set_map('coracao')
                self.assertEqual(net.map_key, 'coracao')
                net.set_map('deserto')  # nao existe
                self.assertEqual(net.map_key, 'coracao')
                self.assertEqual(maps.next_map('coracao'), maps.available()[0])
                net.status = 'playing'
                net.set_map('timo')  # fora do lobby nao muda
                self.assertEqual(net.map_key, 'coracao')
                self.assertEqual(saved, [('map', 'coracao')])  # a escolha do anfitriao e lembrada
            finally:
                settings.set_value = original
        finally:
            game.close()

    def test_layout_select_switches_markers(self):
        layout.select('timo')
        self.assertEqual(layout.MAP_KEY, 'timo')
        self.assertEqual(layout.MODE, 'escort')
        timo_recon = layout.RECON
        layout.select('coracao')
        self.assertEqual(layout.MODE, 'convoy')
        self.assertEqual(len(layout.VALVES), 2)
        self.assertNotEqual(layout.RECON, timo_recon)
        layout.select('bairro')
        self.assertEqual(layout.MODE, 'escort')
        self.assertEqual(layout.VALVES, [])


if __name__ == '__main__':
    unittest.main()
