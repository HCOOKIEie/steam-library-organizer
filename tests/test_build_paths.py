import unittest

from scripts.verify_build_paths import validate_manifest


class BuildPathTests(unittest.TestCase):
    def test_wrapped_space_path_uses_complete_literal(self):
        text = "[('module', 'F:\\\\steam '\n 'lm\\\\.venv-release\\\\Lib\\\\site-packages\\\\module.py', 'PYMODULE')]"
        validate_manifest(text, r'F:\steam lm\.venv-release')

    def test_foreign_site_packages_rejected_even_alongside_allowed_path(self):
        text = repr([r'F:\steam lm\.venv-release\Lib\site-packages\ok.py',
                     r'C:\Python\Lib\site-packages\foreign.py'])
        with self.assertRaisesRegex(ValueError, 'site-packages outside'):
            validate_manifest(text, r'F:\steam lm\.venv-release')

    def test_version_resource_calls_are_parsed_without_execution(self):
        validate_manifest("('app.exe', VSVersionInfo(ffi=FixedFileInfo(filevers=(1, 1, 0, 0))))",
                          r'F:\steam lm\.venv-release')

    def test_foreign_venv_and_contaminated_paths_rejected(self):
        for path in [r'F:\other\.venv\module.py', r'C:\Miniconda3\Lib\module.py',
                     r'C:\Users\Example\AppData\Roaming\Python\module.py']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_manifest(repr([path]), r'F:\steam lm\.venv-release')


if __name__ == '__main__':
    unittest.main()
