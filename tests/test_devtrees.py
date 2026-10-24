import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / 'devtrees.py'
DISCOVERY_ENV = {key: value for key, value in os.environ.items()
                 if not key.startswith('GIT_')}
DISCOVERY_ENV.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
TOP = subprocess.check_output(
    ['git', '-C', str(REPO), 'rev-parse', '--show-toplevel'],
    env=DISCOVERY_ENV, text=True).rstrip('\n')
if Path(TOP).resolve() != REPO:
    raise RuntimeError('test checkout does not match the Git working directory')
GITDIR = Path(subprocess.check_output(
    ['git', '-C', str(REPO), 'rev-parse', '--absolute-git-dir'],
    env=DISCOVERY_ENV, text=True).rstrip('\n'))
FIXTURES = GITDIR / 'stateless-test-fixtures'
if FIXTURES.is_symlink():
    raise RuntimeError('test fixture directory must not be a symlink')
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
        wrapper = '\n'.join([
            'import os, runpy, sys',
            'def guard(event, args):',
            '    if event == "shutil.rmtree":',
            '        raise RuntimeError("DELETION_ATTEMPT: " + os.fspath(args[0]))',
            'sys.addaudithook(guard)',
            'sys.argv = sys.argv[1:]',
            'runpy.run_path(sys.argv[0], run_name="__main__")',
        ])
        return subprocess.run([sys.executable, '-c', wrapper, str(CLI), *map(str, args)],
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

    def test_trailing_space_path_survives_listing_and_dry_run(self):
        workspace, _ = self.setup_clone()
        clone = workspace / 'task with a trailing space '
        result = self.cli('add', '-b', 'space-path', clone, cwd=workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('-C', str(clone), 'status', '--porcelain'), '')
        result = self.cli('list', cwd=workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(clone), result.stdout.splitlines())
        result = self.cli('remove', '--dry-run', clone)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(clone.exists())

    def test_init_seeds_a_full_bare_hub_from_a_normal_checkout(self):
        self.git('-C', str(self.seed), 'commit', '--allow-empty', '-qm', 'Second commit')
        (self.seed / 'local-only.txt').write_text('not committed\n')
        before = (self.seed / '.git/config').read_bytes()
        workspace = self.root / 'project'
        result = self.cli('init', workspace, self.seed)
        self.assertEqual(result.returncode, 0, result.stderr)
        hub = workspace / 'hub.git'
        self.assertTrue(hub.is_dir())
        self.assertEqual(self.git('-C', str(hub), 'rev-parse', '--is-bare-repository').strip(), 'true')
        self.assertEqual(self.git('-C', str(hub), 'rev-parse', '--is-shallow-repository').strip(), 'false')
        self.assertEqual(self.git('-C', str(hub), 'rev-list', '--count', 'main').strip(), '2')
        self.assertIn(str(hub), (workspace / '.devtrees').read_text())
        self.assertNotIn('local-only.txt', self.git('-C', str(hub), 'ls-tree', '--name-only', 'main'))
        self.assertEqual((self.seed / '.git/config').read_bytes(), before)

    def test_two_agents_push_to_hub_then_original_fetches_and_merges(self):
        workspace, first = self.setup_clone()
        hub = workspace / 'hub.git'
        self.assertEqual(self.git('-C', str(first), 'remote', 'get-url', 'origin').strip(), str(hub))
        second = workspace / 'task-b'
        result = self.cli('add', '-b', 'task-b', second, cwd=workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        original_tip = self.git('-C', str(self.seed), 'rev-parse', 'HEAD')
        for clone, branch in ((first, 'task-a'), (second, 'task-b')):
            (clone / (branch + '.txt')).write_text(branch + '\n')
            self.git('-C', str(clone), 'add', branch + '.txt')
            self.git('-C', str(clone), 'commit', '-qm', branch)
            self.git('-C', str(clone), 'push', 'origin', branch)
        self.assertEqual(self.git('-C', str(self.seed), 'rev-parse', 'HEAD'), original_tip)
        self.git('-C', str(self.seed), 'remote', 'add', 'devtrees', str(hub))
        self.git('-C', str(self.seed), 'fetch', 'devtrees')
        self.git('-C', str(self.seed), 'merge', '--ff-only', 'devtrees/task-a')
        self.git('-C', str(self.seed), 'merge', '--no-edit', 'devtrees/task-b')
        for branch in ('task-a', 'task-b'):
            self.assertEqual((self.seed / (branch + '.txt')).read_text(), branch + '\n')
        self.assertEqual(self.git('-C', str(hub), 'rev-parse', 'main'), original_tip)

    def test_init_refuses_a_shallow_source(self):
        shallow = self.fixture / 'shallow-source'
        self.git('clone', '-q', '--no-local', '--depth=1', str(self.seed), str(shallow))
        workspace = self.root / 'project'
        result = self.cli('init', workspace, shallow)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((workspace / '.devtrees').exists())
        self.assertTrue(shallow.exists())

    def test_listing_discovers_unregistered_native_clone(self):
        workspace, clone = self.setup_clone()
        manual = workspace / 'created-by-git'
        self.git('clone', '-q', str(self.remote), str(manual))
        result = self.cli('list', cwd=workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), {str(clone), str(manual)})
        self.assertEqual({p.name for p in workspace.iterdir()}, {'.devtrees', 'hub.git', clone.name, manual.name})

    def test_push_handoff_works_without_workspace_config(self):
        workspace, clone = self.setup_clone()
        result = self.cli('push', clone, str(self.remote), 'task-a')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('refs/heads/task-a', self.git('ls-remote', str(self.remote)))

    def test_unset_root_and_outward_symlink_refuse_before_creation(self):
        env = self.env.copy()
        env.pop('devtrees_root')
        result = self.cli('init', self.root / 'missing-root', self.remote, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'missing-root').exists())
        outside = self.fixture / 'outside'
        outside.mkdir()
        (self.root / 'escape').symlink_to(outside, target_is_directory=True)
        result = self.cli('init', self.root / 'escape/project', self.remote)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_existing_destination_is_not_overwritten(self):
        workspace, clone = self.setup_clone()
        before = (clone / 'tracked.txt').read_bytes()
        result = self.cli('add', clone, cwd=workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((clone / 'tracked.txt').read_bytes(), before)

    def test_full_clone_mode_and_nearest_configuration(self):
        workspace = self.root / 'project'
        result = self.cli('init', workspace, self.remote)
        self.assertEqual(result.returncode, 0, result.stderr)
        inner = workspace / 'inner'
        result = self.cli('init', inner, self.remote, '--clone-mode', 'full', cwd=workspace)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('add', inner / 'clone', cwd=inner)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((inner / 'clone/.git/shallow').exists())

    def test_config_cannot_widen_shell_root(self):
        workspace = self.root / 'project'
        workspace.mkdir()
        (workspace / '.devtrees').write_text('export devtrees_repo=' + str(self.remote) + '\nexport devtrees_root=/\n')
        outside = self.fixture / 'forbidden'
        result = self.cli('add', outside, cwd=workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(outside.exists())

    def test_removal_readiness_belongs_to_the_harness(self):
        _, clone = self.setup_clone()
        (clone / 'tracked.txt').write_text('uncommitted work\n')
        (clone / 'untracked.txt').write_text('local file\n')
        (clone / '.git/local-notes.txt').write_text('private records\n')
        result = self.cli('remove', '--please', clone)
        self.assertIn('DELETION_ATTEMPT: ' + str(clone), result.stderr)
        self.assertTrue(clone.is_dir())

    def test_add_uses_normal_git_templates(self):
        templates = self.fixture / 'templates'
        templates.mkdir()
        (templates / 'template-note.txt').write_text('standard Git template handling\n')
        self.env['GIT_TEMPLATE_DIR'] = str(templates)
        _, clone = self.setup_clone()
        self.assertTrue((clone / '.git/template-note.txt').is_file())
        self.assertEqual((clone / '.git/template-note.txt').read_text(),
                         'standard Git template handling\n')

    def test_removal_defaults_to_dry_run(self):
        workspace, clone = self.setup_clone()
        for command in ('remove', 'teardown'):
            result = self.cli(command, clone)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Dry run', result.stdout)
            self.assertTrue(clone.is_dir())
            self.assertTrue((workspace / 'hub.git').is_dir())
            self.assertNotIn('DELETION_ATTEMPT:', result.stderr)

    def test_explicit_dry_run_preserves_local_data(self):
        workspace, clone = self.setup_clone()
        marker = clone / 'untracked.txt'
        marker.write_text('retain this data\n')
        result = self.cli('remove', '--dry-run', clone)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Dry run', result.stdout)
        self.assertIn(repr(str(clone)), result.stdout)
        self.assertEqual(marker.read_text(), 'retain this data\n')
        self.assertFalse((self.root / '.devtrees-quarantine').exists())
        self.assertEqual({p.name for p in workspace.iterdir()}, {'.devtrees', 'hub.git', clone.name})

    def test_removal_protects_project_hub_and_root(self):
        workspace, clone = self.setup_clone()
        self.git('init', '-q', str(workspace))
        before = (workspace / '.devtrees').read_bytes()
        for target in (workspace, workspace / 'hub.git', self.root):
            result = self.cli('remove', '--please', target)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('DELETION_ATTEMPT:', result.stderr)
            self.assertTrue(target.is_dir())
        self.assertTrue(clone.is_dir())
        self.assertEqual((workspace / '.devtrees').read_bytes(), before)

    def test_removal_refuses_outside_paths_and_selected_symlinks(self):
        _, clone = self.setup_clone()
        alias = self.root / 'alias'
        alias.symlink_to(clone, target_is_directory=True)
        outside = self.fixture / 'outside-clone'
        self.git('clone', '-q', str(self.remote), str(outside))
        for target in (alias, outside):
            result = self.cli('remove', '--please', target)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('DELETION_ATTEMPT:', result.stderr)
        self.assertTrue(clone.is_dir())
        self.assertTrue(outside.is_dir())

    def test_removal_modes_are_mutually_exclusive(self):
        _, clone = self.setup_clone()
        for flags in (('--please', '--dry-run'), ('--please', '--quarantine'), ('--execute',)):
            result = self.cli('remove', clone, *flags)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('DELETION_ATTEMPT:', result.stderr)
            self.assertTrue(clone.is_dir())

    def test_noninteractive_quarantine_cannot_approve_itself(self):
        _, clone = self.setup_clone()
        result = self.cli('remove', '--quarantine', clone, data='quarantine\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('terminal', result.stderr)
        self.assertTrue(clone.exists())
        self.assertFalse((self.root / '.devtrees-quarantine').exists())

    def test_quarantine_will_not_select_a_symlink(self):
        _, clone = self.setup_clone()
        alias = self.root / 'alias'
        alias.symlink_to(clone, target_is_directory=True)
        result = self.cli('remove', '--dry-run', alias)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stderr)
        self.assertTrue(clone.exists())

    def test_preview_does_not_inspect_clone_contents(self):
        _, clone = self.setup_clone()
        target = 'missing\npretend approval'
        (clone / 'odd-link').symlink_to(target)
        result = self.cli('remove', '--dry-run', clone)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(repr(target), result.stdout)
        self.assertEqual(os.readlink(clone / 'odd-link'), target)

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
        self.assertIn('refs/heads/task-a', self.git('ls-remote', str(workspace / 'hub.git')))
        self.assertEqual({p.name for p in workspace.iterdir()}, {'.devtrees', 'hub.git', clone.name})
        self.assertFalse(any('devtrees' in p.name for p in (clone / '.git').iterdir()))


if __name__ == '__main__':
    unittest.main()
