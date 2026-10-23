import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / 'devtrees.py'
GITDIR = Path(subprocess.check_output(
    ['git', '-C', str(REPO), 'rev-parse', '--absolute-git-dir'], text=True).strip())
FIXTURES = GITDIR / 'stateless-test-fixtures'
FIXTURES.mkdir(exist_ok=True)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Path(tempfile.mkdtemp(prefix='run-', dir=FIXTURES))
        self.root = self.fixture / 'environments'
        self.root.mkdir()
        self.env = os.environ.copy()
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                     'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES',
                     'GIT_COMMON_DIR', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT'):
            self.env.pop(name, None)
        self.env.update(devtrees_root=str(self.root),
                        GIT_AUTHOR_NAME='Devtrees Tests',
                        GIT_AUTHOR_EMAIL='tests@example.invalid',
                        GIT_COMMITTER_NAME='Devtrees Tests',
                        GIT_COMMITTER_EMAIL='tests@example.invalid')
        self.seed = self.fixture / 'seed'
        self.git('init', '-q', '-b', 'main', str(self.seed))
        (self.seed / 'tracked.txt').write_text('initial\n')
        self.git('-C', str(self.seed), 'add', 'tracked.txt')
        self.git('-C', str(self.seed), 'commit', '-qm', 'Initial fixture')
        self.remote = self.fixture / 'remote.git'
        self.git('clone', '-q', '--bare', str(self.seed), str(self.remote))

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.fixture,
                                       env=self.env, stderr=subprocess.STDOUT, text=True)

    def cli(self, *args, cwd=None, env=None, data=None):
        return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              cwd=cwd or self.root, env=env or self.env,
                              input=data, capture_output=True, text=True)

    def setup_clone(self):
        workspace = self.root / 'project'
        result = self.cli('init', workspace, self.remote)
        self.assertEqual(result.returncode, 0, result.stderr)
        clone = workspace / 'task with spaces'
        result = self.cli('add', '-b', 'task-a', clone, cwd=workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        return workspace, clone

    def test_setup_clone_and_native_git_push_without_registry(self):
        workspace, clone = self.setup_clone()
        self.assertTrue((clone / '.git').is_dir())
        self.assertFalse((clone / '.git/objects/info/alternates').exists())
        self.assertEqual(self.git('-C', str(clone), 'branch', '--show-current').strip(), 'task-a')
        self.assertTrue((clone / '.git/shallow').exists())
        clean_env = self.env.copy()
        clean_env.pop('devtrees_root')
        pushed = subprocess.run(['git', '-C', str(clone), 'push', 'origin', 'task-a'],
                                env=clean_env, capture_output=True, text=True)
        self.assertEqual(pushed.returncode, 0, pushed.stderr)
        self.assertIn('refs/heads/task-a', self.git('ls-remote', str(self.remote)))
        self.assertEqual({p.name for p in workspace.iterdir()}, {'.devtrees', clone.name})
        self.assertFalse(any('devtrees' in p.name for p in (clone / '.git').iterdir()))


if __name__ == '__main__':
    unittest.main()
