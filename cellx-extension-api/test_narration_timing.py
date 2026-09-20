import tempfile
import unittest
from unittest.mock import patch
import narration_timing as timing

class TimingTests(unittest.TestCase):
    def test_language_and_voice_budgets(self):
        for voice in timing.SPEEDS:
            self.assertGreater(timing.budget(55,voice,4),timing.budget(40,voice,4))
        self.assertGreater(timing.budget(40,'zh-female',4),timing.budget(40,'en-female',4))
        self.assertEqual(timing.units('你好，欢迎。','zh-CN'),4)
        self.assertEqual(timing.units("A well-lit room isn't dark.",'en'),5)

    def test_speed_correction_measured_without_padding(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(timing.subprocess,'run') as run,patch.object(timing,'probe',side_effect=[20.,20.]):
            measured,tempo=timing.correct(folder,[18.,18.],40)
            self.assertEqual(sum(measured),40);self.assertEqual(tempo,.9)
            command=run.call_args.args[0]
            self.assertIn('atempo=0.90000000',command);self.assertNotIn('apad',command);self.assertNotIn('-t',command)
        with self.assertRaises(ValueError):timing.correct('.', [10.],55)

    def test_gpu_near_boundary_clamps_without_exceeding_speed_limit(self):
        raw=[7.08,6.72,6.696,5.952,6.432,5.088,5.712,6.48,5.88,5.856]
        with tempfile.TemporaryDirectory() as folder,patch.object(timing.subprocess,'run'),patch.object(timing,'probe',side_effect=[x/1.12 for x in raw]):
            measured,tempo=timing.correct(folder,raw,55,tolerance=1.5)
            self.assertEqual(tempo,1.12);self.assertAlmostEqual(sum(measured),55.2642857)
        with self.assertRaises(ValueError):timing.correct('.', [80],55,tolerance=1.5)

if __name__=='__main__':unittest.main()
