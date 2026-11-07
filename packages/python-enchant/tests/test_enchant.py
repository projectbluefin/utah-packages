import unittest
import sys
import enchant

class TestEnchant(unittest.TestCase):

    def test_dummy(self):
        self.assertEqual(True, True)

    @unittest.expectedFailure
    def test_expected_failure(self):
        self.assertEqual(False, True)

    def test_en_US(self):
        d = enchant.Dict('en_US')
        self.assertEqual(d.check('enchant'), True)
        self.assertEqual(d.check('enchnt'), False)
        self.assertEqual(
            d.suggest('enchnt'),
            ['enchant', 'entrench', 'tench'])

    def test_de_DE(self):
        d = enchant.Dict('de_DE')
        self.assertEqual(d.check('Alpenglühen'), True)
        self.assertEqual(d.check('Alpengluhen'), False)
        self.assertEqual(
            d.suggest('Alpengluhen'),
            ['Alpenglühen', 'Alpengluten', 'Altenglischen'])

if __name__ == "__main__":
    unittest.main()
