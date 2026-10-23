"""Check fixture allocation before the main test module runs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
ENV = {key: value for key, value in os.environ.items()
       if not key.startswith('GIT_')}
ENV.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
           PYTHONDONTWRITEBYTECODE='1')


class BootstrapTests(unittest.TestCase):
    def test_foreign_git_context_cannot_redirect_fixture_storage(self):
        top = subprocess.check_output(
            ['git', '-C', str(REPO), 'rev-parse', '--show-toplevel'],
            env=ENV, text=True).rstrip('\n')
        self.assertEqual(Path(top).resolve(), REPO)
        admin = Path(subprocess.check_output(
            ['git', '-C', str(REPO), 'rev-parse', '--absolute-git-dir'],
            env=ENV, text=True).rstrip('\n'))
        fixture = Path(tempfile.mkdtemp(prefix='bootstrap-', dir=admin))
        foreign = fixture / 'foreign'
        subprocess.run(['git', 'init', '-q', str(foreign)], env=ENV, check=True)
        poisoned = dict(ENV, GIT_DIR=str(foreign / '.git'),
                        GIT_WORK_TREE=str(foreign),
                        GIT_COMMON_DIR=str(foreign / '.git'),
                        GIT_INDEX_FILE=str(foreign / '.git/foreign-index'))
        result = subprocess.run(
            [sys.executable, '-c',
             'import runpy,sys; runpy.run_path(sys.argv[1], run_name="bootstrap_probe")',
             str(REPO / 'tests/test_devtrees.py')],
            cwd=REPO, env=poisoned, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((foreign / '.git/stateless-test-fixtures').exists())
        self.assertFalse((foreign / '.git/foreign-index').exists())


if __name__ == '__main__':
    unittest.main()
