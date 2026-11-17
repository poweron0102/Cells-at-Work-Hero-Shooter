"""Integracao dos kits: passivas, RMB/Q/E/F e objetos de habilidade (motor real, sem GPU)."""
import math
import unittest
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.session import connect
from UserComponents.cells.catalog import HEROES, BALANCE


class KitTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, "127.0.0.1", 0, True, "Kit test")
        self.net.start(True)
        for p in self.net.roster.value.values():
            p["bot"] = False
        self.arena = mount_arena(self.game)
        for _ in range(60):
            step(self.game)
        # Celula (slot 0) em z=60 olhando para -z; bacteria (slot 3) em z=54 olhando para +z.
        self.cell, self.bact = self.arena.actors[0], self.arena.actors[3]
        self.cell.body.teleport(Vec3(0, 1, 60))
        self.bact.body.teleport(Vec3(0, 1, 54))
        self.cell.yaw = self.cell.pitch = self.bact.pitch = 0
        self.bact.yaw = math.pi
        self.settle()

    def tearDown(self):
        self.game.close()

    def settle(self, seconds=1/60):
        for _ in range(max(1, int(seconds*60))):
            step(self.game)

    def hero(self, actor, key):
        actor.hero = key
        actor.reset_kit()
        actor.health.value = HEROES[key].health
        actor.shield.value = 0
        actor.weapon.ammo = HEROES[key].magazine

    def total(self, actor):
        return actor.health.value+actor.shield.value

    def tap(self, actor, key):
        actor.controls = {key: True}
        self.settle()
        actor.controls = {}
        self.settle()

    def shoot(self, actor):
        actor.weapon.timer = actor.weapon.reload_time = 0
        actor.weapon.ammo = HEROES[actor.hero].magazine
        actor.weapon.fire()

    # -- Macrofago ------------------------------------------------------------
    def test_engulf_eats_shots_from_the_front_and_charges_the_special(self):
        self.hero(self.cell, 'macrophage')
        self.cell.controls = dict(secondary=True)
        self.settle()
        self.assertEqual(self.cell.front, 'engulf')
        health, charge = self.total(self.cell), self.cell.charge
        self.shoot(self.bact)
        self.assertEqual(self.total(self.cell), health)
        self.assertGreater(self.cell.charge, charge)
        # Pelas costas a membrana nao protege.
        self.bact.body.teleport(Vec3(0, 1, 66))
        self.bact.yaw = 0
        self.settle()
        self.shoot(self.bact)
        self.assertLess(self.total(self.cell), health)

    def test_engulf_bar_runs_out_and_locks(self):
        self.hero(self.cell, 'macrophage')
        self.cell.controls = dict(secondary=True)
        self.settle(BALANCE['engulf_time']+.3)
        self.assertIsNone(self.cell.front)
        self.assertGreater(self.cell.engulf_lock, 0)

    def test_feast_shares_shields_and_spit_hits_the_front(self):
        self.hero(self.cell, 'macrophage')
        self.cell.charge = 100
        self.tap(self.cell, 'ultimate')
        self.assertTrue(self.cell.ult_on)
        self.assertGreater(self.cell.ult_cam, 0)
        self.cell.controls = dict(secondary=True)
        self.settle()
        self.assertAlmostEqual(self.cell.front_radius, BALANCE['engulf_radius']*2)
        self.shoot(self.bact)
        self.assertGreater(self.cell.feast, 0)
        self.assertGreater(self.cell.shield.value, 0)
        before = self.total(self.bact)
        self.cell.controls = dict(ultimate=True)
        self.settle()
        self.assertFalse(self.cell.ult_on)
        self.assertLess(self.total(self.bact), before-40)

    def test_pseudopod_pulls_the_target(self):
        self.hero(self.cell, 'macrophage')
        self.bact.body.teleport(Vec3(0, 1, 48))
        self.settle()
        self.tap(self.cell, 'ability')
        self.settle(.4)
        self.assertGreater(self.bact.transform.z, 49.5)

    # -- B-Cell ---------------------------------------------------------------
    def test_turret_is_placed_by_click_then_shoots_and_marks(self):
        self.hero(self.cell, 'b_cell')
        self.cell.pitch = -.5
        self.tap(self.cell, 'ability')
        self.assertEqual(self.cell.placing, 'turret')
        self.assertIsNotNone(self.cell.place)
        self.tap(self.cell, 'fire')
        turrets = [m for m in self.arena.minions.values() if m['kind'] == 'turret']
        self.assertEqual(len(turrets), 1)
        self.assertGreater(self.cell.ability_cd, 0)
        health = self.total(self.bact)
        self.settle(1.2)
        self.assertLess(self.total(self.bact), health)
        self.assertGreater(self.bact.marked, 0)

    def test_enemies_destroy_the_turret(self):
        self.hero(self.cell, 'b_cell')
        self.arena.spawn_minion(1, 'turret', 0, (0, self.bact.feet[1], 57), 0, BALANCE['turret_health'], 0)
        self.bact.pitch = -.12
        for _ in range(30):
            self.shoot(self.bact)
            if 1 not in self.arena.minions:
                break
        self.assertNotIn(1, self.arena.minions)

    def test_mark_raises_damage_and_killer_t_exploits_it(self):
        self.bact.shield.value = 0
        self.bact.marked = 5
        health = self.bact.health.value
        self.bact.damage(100, self.cell)
        self.assertAlmostEqual(health-self.bact.health.value, 100*(1+BALANCE['mark_bonus']))
        self.hero(self.cell, 'killer_t')
        health = self.bact.health.value
        self.bact.damage(100, self.cell)
        self.assertAlmostEqual(health-self.bact.health.value, 100*1.2*(1+BALANCE['mark_bonus']))

    def test_antibody_grenade_marks_in_area(self):
        self.hero(self.cell, 'b_cell')
        self.cell.pitch = -.1
        self.tap(self.cell, 'ability2')
        self.assertTrue(self.arena.projectiles)
        self.settle(1.5)
        self.assertGreater(self.bact.marked, 0)
        self.assertLess(self.total(self.bact), HEROES[self.bact.hero].health+70)

    # -- Killer T / Neutrofilo ------------------------------------------------
    def test_perforin_bursts_after_delay(self):
        self.hero(self.cell, 'killer_t')
        self.hero(self.bact, 'staphylococcus')
        self.tap(self.cell, 'ability2')
        self.assertTrue(self.bact.perforin)
        after_hit = self.bact.health.value
        self.settle(3.2)
        self.assertLessEqual(self.bact.health.value, after_hit-55)

    def test_net_roots_the_target(self):
        self.tap(self.cell, 'ability2')
        self.assertGreater(self.bact.root, 0)
        start = self.bact.transform.position
        self.bact.controls = dict(z=1.0)
        self.settle(.6)
        moved = (self.bact.transform.position-start).magnitude()
        self.assertLess(moved, .2)

    def test_backstab_doubles_knife_damage(self):
        self.hero(self.bact, 'staphylococcus')
        self.bact.body.teleport(Vec3(0, 1, 58.6))
        self.bact.yaw = math.pi
        self.settle()
        health = self.bact.health.value
        self.cell.secondary()
        front = health-self.bact.health.value
        self.bact.health.value = health
        self.bact.yaw = 0  # de costas para a celula
        self.cell.secondary_cd = 0
        self.cell.secondary()
        self.assertAlmostEqual(health-self.bact.health.value, front*2)

    # -- Bacterias ------------------------------------------------------------
    def test_barrier_blocks_until_broken(self):
        self.hero(self.bact, 'pneumococcus')
        self.bact.shield.value = 70
        self.bact.controls = dict(secondary=True)
        self.settle()
        self.assertEqual(self.bact.front, 'barrier')
        health = self.total(self.bact)
        self.shoot(self.cell)
        self.assertEqual(self.total(self.bact), health)
        self.assertLess(self.bact.barrier_hp, BALANCE['barrier_health'])
        self.bact.take_absorb(BALANCE['barrier_health'])
        self.assertIsNone(self.bact.front)
        self.assertGreater(self.bact.barrier_lock, 0)

    def test_coagulase_wall_blocks_shots_then_expires(self):
        y = self.cell.feet[1]
        self.arena.add_wall(7, (0, y, 57), 0, 1.0)
        self.settle()
        health = self.total(self.bact)
        self.shoot(self.cell)
        self.assertEqual(self.total(self.bact), health)
        self.settle(1.2)
        self.assertFalse(self.arena.walls)
        self.shoot(self.cell)
        self.assertLess(self.total(self.bact), health)

    def test_staph_places_wall_with_preview(self):
        self.hero(self.bact, 'staphylococcus')
        self.bact.pitch = -.4
        self.tap(self.bact, 'ability')
        self.assertEqual(self.bact.placing, 'wall')
        self.tap(self.bact, 'fire')
        self.assertEqual(len(self.arena.walls), 1)

    def test_toxin_blocks_regeneration(self):
        self.hero(self.bact, 'staphylococcus')
        self.tap(self.bact, 'ability2')
        self.assertGreater(self.cell.antiheal, 0)
        self.cell.health.value = 100
        self.cell.since_hit = 10
        self.settle(1)
        self.assertLessEqual(self.cell.health.value, 100)

    def test_dome_blocks_shots_from_outside(self):
        self.hero(self.bact, 'staphylococcus')
        self.cell.body.teleport(Vec3(0, 1, 64))
        self.settle()
        self.bact.charge = 100
        self.tap(self.bact, 'ultimate')
        self.assertTrue(any(z['kind'] == 'dome' for z in self.arena.zones))
        health = self.total(self.bact)
        self.shoot(self.cell)
        self.assertEqual(self.total(self.bact), health)
        self.cell.body.teleport(Vec3(0, 1, 57))
        self.settle()
        self.shoot(self.cell)
        self.assertLess(self.total(self.bact), health)

    def test_acid_grenade_aims_then_throws_on_release(self):
        self.hero(self.bact, 'pseudomonas')
        self.bact.pitch = -.2
        self.bact.controls = dict(secondary=True)
        self.settle(.2)
        self.assertTrue(self.bact.aiming)
        self.assertIsNotNone(self.bact.arc)
        health = self.total(self.cell)
        self.bact.controls = {}
        self.settle()
        self.assertTrue(self.arena.projectiles)
        self.settle(1.2)
        self.assertLess(self.total(self.cell), health)

    def test_streptococcus_dash_has_two_charges(self):
        self.hero(self.bact, 'streptococcus')
        self.tap(self.bact, 'ability')
        self.tap(self.bact, 'ability')
        self.assertEqual(self.bact.q_charges, 0)
        self.bact.ability()
        self.assertEqual(self.bact.q_charges, 0)
        self.settle(HEROES['streptococcus'].ability_cd+.1)
        self.assertEqual(self.bact.q_charges, 1)

    def test_binary_fission_spawns_two_clones(self):
        self.hero(self.bact, 'streptococcus')
        self.bact.charge = 100
        self.tap(self.bact, 'ultimate')
        clones = [m for m in self.arena.minions.values() if m['kind'] == 'clone']
        self.assertEqual(len(clones), 2)
        self.settle(10.5)
        self.assertFalse([m for m in self.arena.minions.values() if m['kind'] == 'clone'])

    def test_pneumonia_cloud_follows_and_hurts(self):
        self.hero(self.bact, 'pneumococcus')
        self.bact.charge = 100
        self.tap(self.bact, 'ultimate')
        cloud = next(z for z in self.arena.zones if z['kind'] == 'cloud')
        self.bact.body.teleport(Vec3(0, 1, 57))
        health = self.total(self.cell)
        self.settle(.5)
        self.assertAlmostEqual(cloud['pos'][2], self.bact.transform.z, delta=.2)
        self.assertLess(self.total(self.cell), health)

    def test_tap_g_delivers_resources_instead_of_building(self):
        state = self.arena.state
        state.resources[3] = BALANCE['colony_cost']
        state.add_colony(3, self.bact.feet)
        state.resources[3] = 4
        self.bact.controls = dict(build=True)
        self.settle(.3)
        self.assertEqual(state.resources[3], 0)
        self.assertIsNone(self.bact.build)
        self.assertGreater(state.colonies[0]['dev'], 0)


if __name__ == "__main__":
    unittest.main()
