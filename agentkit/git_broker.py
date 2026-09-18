"""Trusted local Git broker for controller-created disposable repositories."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess


class GitBrokerError(ValueError):
    pass


OID = re.compile(r'^[0-9a-f]{40,64}$')
SAFE = re.compile(r'^[A-Za-z0-9._/-]+$')


class GitBroker:
    def __init__(self, managed_root):
        self.root = Path(managed_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.repositories = self.root / 'repositories'
        self.worktrees = self.root / 'worktrees'
        self.worker_copies = self.root / 'worker-copies'
        self.review_copies = self.root / 'review-copies'
        for path in (self.repositories, self.worktrees, self.worker_copies, self.review_copies):
            path.mkdir(exist_ok=True, mode=0o700)

    def _inside(self, path, parent=None):
        path = Path(path).resolve()
        parent = (parent or self.root).resolve()
        if path == parent or parent not in path.parents:
            raise GitBrokerError('path escapes managed root')
        return path

    def _git(self, repository, *args, cwd=None):
        repository = self._inside(repository, self.repositories)
        argv = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false',
                '-C', str(repository), *args]
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'LC_ALL')}
        env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                   GIT_AUTHOR_NAME='Agentkit Controller', GIT_AUTHOR_EMAIL='controller@localhost',
                   GIT_COMMITTER_NAME='Agentkit Controller', GIT_COMMITTER_EMAIL='controller@localhost')
        run = subprocess.run(argv, cwd=str(cwd or repository), env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=20, check=False)
        if run.returncode:
            raise GitBrokerError(run.stderr.decode('utf-8', 'replace'))
        return run.stdout.decode('utf-8', 'strict').strip()

    def create_repository(self, name, files):
        if not SAFE.fullmatch(name) or '/' in name:
            raise GitBrokerError('invalid repository name')
        repository = self.repositories / name
        if repository.exists() or repository.is_symlink():
            raise GitBrokerError('repository already exists')
        repository.mkdir(mode=0o700)
        subprocess.run(['git', 'init', '-b', 'main', str(repository)], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True, timeout=20)
        for relative, content in files.items():
            target = self._safe_relative(repository, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self._git(repository, 'add', '--', *sorted(files))
        self._git(repository, 'commit', '-m', 'Seed disposable fixture')
        return repository, self.revision(repository, 'HEAD')

    def _safe_relative(self, root, relative):
        if not isinstance(relative, str) or not relative or relative.startswith('/') or not SAFE.fullmatch(relative):
            raise GitBrokerError('invalid relative path')
        target = (Path(root) / relative).resolve()
        root = Path(root).resolve()
        if root not in target.parents or target == root:
            raise GitBrokerError('path traversal')
        return target

    def revision(self, repository, revision):
        value = self._git(repository, 'rev-parse', '--verify', revision + '^{commit}')
        if not OID.fullmatch(value):
            raise GitBrokerError('invalid Git revision')
        return value

    def create_task_worktree(self, repository, task_id, base_revision):
        base = self.revision(repository, base_revision)
        branch = 'agentkit/' + task_id
        if not SAFE.fullmatch(branch):
            raise GitBrokerError('invalid branch')
        worktree = self.worktrees / task_id
        if worktree.exists() or worktree.is_symlink():
            raise GitBrokerError('worktree already exists')
        self._git(repository, 'worktree', 'add', '-b', branch, str(worktree), base)
        return branch, worktree, base

    def _tracked(self, repository, revision):
        text = self._git(repository, 'ls-tree', '-r', '--name-only', revision)
        return [line for line in text.splitlines() if line]

    def export_snapshot(self, repository, revision, destination, *, review=False):
        revision = self.revision(repository, revision)
        destination = Path(destination).resolve()
        expected_parent = self.review_copies if review else self.worker_copies
        self._inside(destination, expected_parent)
        if destination.exists() or destination.is_symlink():
            raise GitBrokerError('snapshot destination must be fresh')
        destination.mkdir(parents=True, mode=0o700)
        for relative in self._tracked(repository, revision):
            mode_type = self._git(repository, 'ls-tree', revision, '--', relative).split()[0]
            if mode_type == '120000':
                raise GitBrokerError('symlink entries are unsupported')
            target = self._safe_relative(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = subprocess.run(['git', '-C', str(repository), 'show', revision + ':' + relative],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=20).stdout
            with target.open('wb') as stream:
                stream.write(content)
        return destination

    def manifest(self, root, *, exclude_git=False):
        root = Path(root).resolve()
        result = {}
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise GitBrokerError('symlink in controlled workspace')
            if path.is_file():
                relative = str(path.relative_to(root))
                if exclude_git and (relative == '.git' or relative.startswith('.git/')):
                    continue
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def worktree_identity(self, repository, worktree):
        repository = self._inside(repository, self.repositories)
        worktree = self._inside(worktree, self.worktrees)
        branch = branch_for_worktree(repository, worktree)
        return {
            'branch': branch,
            'revision': self.revision(repository, branch),
            'clean': self._git(repository, '-C', str(worktree), 'status', '--porcelain=v1',
                               '--untracked-files=all') == '',
            'manifest': self.manifest(worktree, exclude_git=True),
        }

    def apply_worker_changes(self, repository, worktree, worker_copy, allowed_paths, message):
        repository = self._inside(repository, self.repositories)
        worktree = self._inside(worktree, self.worktrees)
        worker_copy = self._inside(worker_copy, self.worker_copies)
        allowed = set(allowed_paths)
        tracked = set(self._tracked(repository, 'HEAD'))
        worker_manifest = self.manifest(worker_copy)
        if set(worker_manifest) != tracked:
            raise GitBrokerError('worker added, removed, or renamed a file')
        changed = []
        for relative in sorted(tracked):
            destination = self._safe_relative(worktree, relative)
            source = self._safe_relative(worker_copy, relative)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != worker_manifest[relative]:
                changed.append(relative)
                if relative not in allowed:
                    raise GitBrokerError('worker changed protected path: ' + relative)
        if not changed:
            raise GitBrokerError('worker produced no changes')
        for relative in changed:
            destination = self._safe_relative(worktree, relative)
            source = self._safe_relative(worker_copy, relative)
            destination.write_bytes(source.read_bytes())
        self._git(repository, '-C', str(worktree), 'add', '--', *changed)
        self._git(repository, '-C', str(worktree), 'commit', '-m', message)
        return self.revision(repository, branch_for_worktree(repository, worktree)), changed

    def diff(self, repository, base, head):
        base = self.revision(repository, base)
        head = self.revision(repository, head)
        return self._git(repository, 'diff', '--no-ext-diff', '--binary', base, head)


def branch_for_worktree(repository, worktree):
    run = subprocess.run(['git', '-C', str(worktree), 'symbolic-ref', '--short', 'HEAD'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10)
    branch = run.stdout.decode().strip()
    if not SAFE.fullmatch(branch):
        raise GitBrokerError('invalid worktree branch')
    return branch
