from math import hypot
from unittest import TestCase

from doku2d import Area, Circle, Game, Polygon, Segment, ShapeCast, StaticBody
from doku2d.physics import Box


class ShapeCastTests(TestCase):
    def setUp(self):
        self.game = Game()
        self.addCleanup(self.game.close)

    def test_circle_reaches_wall_that_a_center_ray_misses(self):
        wall = self.game.add(StaticBody(position=(50, 0), size=(10, 10)))
        start, end = (0, 7), (100, 7)
        self.assertIsNone(self.game.physics.raycast(start, end))
        hit = self.game.physics.shapecast(Circle(3), start, end)
        self.assertIs(hit.collider, wall)
        self.assertAlmostEqual(hit.distance, 45 - 5**.5)
        self.assertAlmostEqual(hit.fraction, hit.distance / 100)
        self.assertAlmostEqual(hit.point.x, 45)
        self.assertAlmostEqual(hit.point.y, 5)
        self.assertAlmostEqual(hypot(*hit.normal), 1)
        self.assertLess(hit.normal.x, 0)
        self.assertGreater(hit.normal.y, 0)

    def test_box_sweep_accounts_for_rotation_and_reports_a_surface_point(self):
        wall = self.game.add(StaticBody(position=(50, 0), size=(10, 12)))
        box = Box((20, 4))
        straight = self.game.physics.shapecast(box, (0, 2), (100, 2))
        rotated = self.game.physics.shapecast(box, (0, 2), (100, 2), rotation=90)
        self.assertIs(straight.collider, wall)
        self.assertIs(rotated.collider, wall)
        self.assertAlmostEqual(straight.distance, 35)
        self.assertAlmostEqual(rotated.distance, 43)
        self.assertAlmostEqual(straight.point.x, 45)
        self.assertAlmostEqual(straight.point.y, 2)
        self.assertEqual(tuple(straight.normal), (-1, 0))

    def test_box_reaches_rounded_segment_without_tunneling(self):
        beam = self.game.add(StaticBody(position=(60, 0), shape=Segment((0, -8), (0, 8), 2)))
        hit = self.game.physics.shapecast(Box((4, 4)), (0, 9), (10_000, 9))
        self.assertIs(hit.collider, beam)
        self.assertAlmostEqual(hit.distance, 56)
        self.assertAlmostEqual(hit.point.x, 58)
        self.assertLessEqual(hit.point.y, 8)

    def test_initial_overlap_and_stationary_queries(self):
        obstacle = self.game.add(StaticBody(position=(30, 10), radius=5))
        for shape in (Box((6, 6)), Circle(3)):
            with self.subTest(shape=shape):
                hit = self.game.physics.shapecast(shape, (30, 10), (30, 10))
                self.assertIs(hit.collider, obstacle)
                self.assertEqual((hit.fraction, hit.distance), (0, 0))
                self.assertAlmostEqual(hypot(hit.point.x - 30, hit.point.y - 10), 5)
                self.assertAlmostEqual(hypot(*hit.normal), 1)
                self.assertIsNone(self.game.physics.shapecast(shape, (0, 0), (0, 0)))

    def test_first_contact_respects_masks_exclusions_and_areas(self):
        barrier = self.game.add(StaticBody(position=(60, 0), size=(6, 16)))
        near = self.game.add(StaticBody(position=(30, 0), size=(6, 16)))
        sensor = self.game.add(Area(position=(10, 0), size=(6, 16)))
        near.collision_layer = 2
        self.game.update(1 / 60)
        box = Box((4, 4))
        cast = self.game.physics.shapecast
        self.assertIs(cast(box, (0, 0), (100, 0)).collider, near)
        self.assertIs(cast(box, (0, 0), (100, 0), mask=1).collider, barrier)
        self.assertIs(cast(box, (0, 0), (100, 0), exclude=(near,)).collider, barrier)
        self.assertIs(cast(box, (0, 0), (100, 0), areas=True).collider, sensor)
        self.assertIsNone(cast(box, (0, 0), (100, 0), mask=4))

    def test_tracking_cast_uses_local_offset_and_ignores_its_target(self):
        actor = self.game.add(StaticBody(position=(20, 5), size=(20, 8)))
        obstacle = self.game.add(StaticBody(position=(17, 50), size=(12, 10)))
        actor.rotation = 90
        cast = self.game.add(ShapeCast(Box((4, 8)), target=actor, position=(2, 3),
                                      target_position=(60, 0)))
        self.game.update(1 / 60)
        self.assertTrue(cast.is_colliding())
        self.assertIs(cast.get_collider(), obstacle)
        self.assertAlmostEqual(cast.get_collision_point().y, 45, places=4)
        self.assertAlmostEqual(cast.get_collision_normal().y, -1, places=5)
        actor.position = (100, 5)
        self.assertIsNone(cast.force_update())
        actor.position = (20, 5)
        self.assertIs(cast.force_update().collider, obstacle)
        self.game.remove(actor)
        self.assertIsNone(cast.force_update())
        cast.enabled = False
        self.assertIsNone(cast.collision)

    def test_invalid_cast_inputs_fail_at_query_time(self):
        cast = self.game.physics.shapecast
        with self.assertRaises(TypeError):
            cast(Polygon(), (0, 0), (30, 0))
        with self.assertRaises(ValueError):
            cast(Circle(2), (0, 0), (float('inf'), 0))
        with self.assertRaises(ValueError):
            cast(Box(), (0, 0), (1, 0), rotation=float('nan'))
