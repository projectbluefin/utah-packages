import unittest
import sys
import subprocess

class TestAppstream(unittest.TestCase):

    def test_dummy(self):
        self.assertEqual(True, True)

    @unittest.expectedFailure
    def test_expected_failure(self):
        self.assertEqual(False, True)

    def test_appstreamcli_search(self):
        cp  = subprocess.run(
            ['env LC_ALL=en_US.UTF-8 appstreamcli search emoji-picker'],
            encoding='UTF-8',
            text=True,
            shell=True,
            capture_output=True)
        output_lines = cp.stdout.split('\n')
        print('----------------------------------------')
        print(output_lines)
        print('----------------------------------------')
        self.assertTrue(
            'Identifier: org.freedesktop.ibus.engine.typing_booster.emoji_picker [desktop-application]'
            in output_lines)
        self.assertTrue(
            'Name: Emoji Picker'
            in output_lines)
        self.assertTrue(
            'Summary: Emoji browsing tool'
            in output_lines)
        self.assertTrue(
            'Homepage: https://mike-fabian.github.io/ibus-typing-booster/'
            in output_lines)
        self.assertTrue(
            'Icon: org.freedesktop.ibus.engine.typing_booster.emoji_picker.png'
            in output_lines)
        # This section not always there, better don’t test for this:
        # self.assertTrue(
        #    'Package: emoji-picker'
        #    in output_lines)

if __name__ == "__main__":
    unittest.main()
