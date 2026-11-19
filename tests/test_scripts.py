"""Behavior tests for scripts/; stdlib unittest only: python3 -m unittest discover -s tests -v"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / 'scripts' / 'check_report.py'
INVENTORY = ROOT / 'scripts' / 'inventory.py'
TEMPLATE = json.loads((ROOT / 'assets' / 'audit-template.json').read_text(encoding='utf-8'))
TMP = Path('/tmp')
# macOS ships /tmp as a root-owned symlink to /private/tmp; Linux usually does not.
OS_LINKED_TMP = (TMP.is_symlink() and TMP.lstat().st_uid == 0
                 and hasattr(os, 'geteuid') and os.geteuid() != 0)


def run(script, *args, env=None):
    # -I: agents run scripts isolated, so each script must not import its siblings.
    return subprocess.run([sys.executable, '-I', str(script), *map(str, args)],
                          capture_output=True, text=True, env=env, timeout=60)


def report():
    data = copy.deepcopy(TEMPLATE)
    data['audit'].update(id='AUD-T', repository='demo', snapshot='abc123, clean tree',
                         started_at='2026-11-18T10:00:00Z', completed_at='2026-11-18T11:00:00Z',
                         completion='complete', working_tree='clean',
                         limitations=['Static review only; no runtime access.'])
    data['coverage'] = [{'id': 'COV-1', 'area': 'core', 'owner': 'coordinator', 'status': 'reviewed',
                         'paths': ['src'], 'checks': ['read handlers'], 'evidence': ['src/a.py:f'], 'gaps': []}]
    data['commands'] = [{'id': 'CMD-1', 'command': 'pytest tests/test_a.py', 'environment': 'local venv',
                         'status': 'failed', 'exit_code': 1, 'summary': 'assertion reproduces double charge'}]
    data['findings'] = [{
        'id': 'AUD-001', 'title': 'Retry double-charges', 'kind': 'defect', 'category': 'data-integrity',
        'severity': 'high', 'confidence': 'high', 'verification': 'reproduced', 'priority': 'P1',
        'effort': 'S', 'fingerprint': 'charge retry without stable key', 'invariant': 'one charge per order',
        'impact': 'duplicate charge', 'recommendation': 'reuse the order key',
        'verification_detail': 'CMD-1 fails on the second charge', 'preconditions': ['provider timeout'],
        'failure_sequence': ['timeout', 'retry', 'second charge'], 'counterevidence': ['no dedupe in client'],
        'validation': ['retry test passes'], 'tradeoffs': ['none material'], 'coverage_ids': ['COV-1'],
        'command_ids': ['CMD-1'], 'sources': [],
        'locations': [{'path': 'src/a.py', 'start_line': 3, 'end_line': 9, 'symbol': 'charge',
                       'observation': 'new key per attempt'}],
        'independent_review': {'status': 'accepted', 'reviewer': 'verifier agent', 'reason': 'trace confirmed'}}]
    data['next_actions'] = [{'id': 'ACT-1', 'priority': 'P1', 'action': 'Fix key', 'finding_ids': ['AUD-001'],
                             'depends_on': [], 'acceptance': 'CMD-1 passes'}]
    return data


class Scratch(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write_report(self, data):
        path = self.dir / 'audit.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path


class CheckReportTest(Scratch):
    def test_valid_report_renders(self):
        out = self.dir / 'out' / 'report.md'
        result = run(CHECK, self.write_report(report()), '--render', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Verified defects: **1**', out.read_text(encoding='utf-8'))

    def test_untouched_template_limitation_is_rejected(self):
        data = report()
        data['audit']['limitations'] = copy.deepcopy(TEMPLATE['audit']['limitations'])
        result = run(CHECK, self.write_report(data))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('replace template values', result.stderr)

    def test_reproduced_without_executed_command_is_rejected(self):
        data = report()
        data['commands'][0].update(status='not-run', exit_code=None)
        result = run(CHECK, self.write_report(data))
        self.assertEqual(result.returncode, 1)
        self.assertIn('reproduced requires an executed command', result.stderr)

    def test_render_rejects_planted_symlink_parent(self):
        real = self.dir / 'real'
        real.mkdir()
        (self.dir / 'link').symlink_to(real)
        result = run(CHECK, self.write_report(report()), '--render', self.dir / 'link' / 'report.md')
        self.assertEqual(result.returncode, 1)
        self.assertIn('render parent cannot be a symlink', result.stderr)
        self.assertEqual(list(real.iterdir()), [])

    @unittest.skipUnless(OS_LINKED_TMP, 'needs a root-owned /tmp symlink (macOS)')
    def test_render_accepts_os_symlinked_tmp(self):
        out = TMP / ('audit-test-' + uuid.uuid4().hex) / 'report.md'
        self.addCleanup(shutil.rmtree, os.path.realpath(out.parent), True)
        result = run(CHECK, self.write_report(report()), '--render', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.is_file())


class InventoryTest(Scratch):
    def setUp(self):
        super().setUp()
        home = self.dir / 'home'
        home.mkdir()
        self.global_config = home / '.gitconfig'
        self.global_config.write_text('[user]\n\tname = t\n\temail = t@example.invalid\n'
                                      '[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n')
        self.env = {**os.environ, 'HOME': str(home), 'GIT_CONFIG_GLOBAL': str(self.global_config),
                    'GIT_CONFIG_SYSTEM': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
        self.repo = self.dir / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        (self.repo / 'a.txt').write_text('one\n')
        self.git('add', 'a.txt')
        self.git('commit', '-qm', 'init')
        (self.repo / 'a.txt').write_text('two\n')

    def git(self, *args):
        subprocess.run(['git', *args], cwd=self.repo, env=self.env, check=True, capture_output=True)

    def inventory(self, *args):
        result = run(INVENTORY, self.repo, *args, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if not args else None

    def test_user_global_filter_does_not_skip_dirty_status(self):
        with self.global_config.open('a') as stream:
            stream.write('[filter "lfs"]\n\tclean = git-lfs clean -- %f\n\tprocess = git-lfs filter-process\n')
        git = self.inventory()['git']
        self.assertTrue(git['status_complete'])
        self.assertEqual([p['path'] for p in git['dirty_paths']], ['a.txt'])

    def test_repository_filter_never_executes(self):
        marker = self.dir / 'filter-ran'
        self.git('config', 'filter.x.clean', f'touch {marker}; cat')
        (self.repo / '.gitattributes').write_text('* filter=x\n')
        data = self.inventory()
        self.assertFalse(marker.exists(), 'inventory executed a repository-defined filter')
        self.assertFalse(data['git']['status_complete'])
        self.git('status', '--porcelain')  # control: the planted filter is live for plain git
        self.assertTrue(marker.exists(), 'test cannot fail: git status did not run the filter')

    def test_repository_lfs_extension_blocks_status(self):
        # A trusted global lfs filter runs lfs.extension commands, which repo config can define.
        with self.global_config.open('a') as stream:
            stream.write('[filter "lfs"]\n\tclean = git-lfs clean -- %f\n\tprocess = git-lfs filter-process\n')
        self.git('config', 'lfs.extension.x.clean', 'touch planted')
        self.assertFalse(self.inventory()['git']['status_complete'])

    def test_output_rejects_planted_symlink_parent(self):
        real = self.dir / 'real'
        real.mkdir()
        (self.dir / 'link').symlink_to(real)
        result = run(INVENTORY, self.repo, '--output', self.dir / 'link' / 'inventory.json', env=self.env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Output parent 'link' is a symlink", result.stderr)
        self.assertEqual(list(real.iterdir()), [])

    @unittest.skipUnless(OS_LINKED_TMP, 'needs a root-owned /tmp symlink (macOS)')
    def test_output_accepts_os_symlinked_tmp(self):
        out = TMP / ('inventory-test-' + uuid.uuid4().hex) / 'inventory.json'
        self.addCleanup(shutil.rmtree, os.path.realpath(out.parent), True)
        self.inventory('--output', out)
        self.assertTrue(out.is_file())


if __name__ == '__main__':
    unittest.main()
