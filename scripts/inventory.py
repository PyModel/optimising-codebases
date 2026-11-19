#!/usr/bin/env python3
"""Bounded, metadata-only candidate inventory; this is not audit coverage.

The inventory does not open source files, configuration values, or symlink
targets. Git may internally inspect tracked files to determine dirty status;
only paths and metadata are captured. Commands have bounded output and
deadlines, disable fsmonitor, and avoid index refresh writes. Existing output
files are never replaced.
"""

from __future__ import annotations

import argparse
import collections
import errno
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import selectors
import shutil
import stat
import subprocess
import sys
import time
import uuid


SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "vendor", "venv", ".venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
    ".next", ".nuxt", ".svelte-kit", ".turbo", "dist", "build", "target",
    "coverage", "Pods", "Carthage", ".terraform", "DerivedData", ".gradle",
})
SENSITIVE_DIRS = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".vault", "secrets"})
RELEVANT_DIRS = (".github", ".gitlab", ".circleci", ".devcontainer")
SENSITIVE_NAMES = frozenset({
    ".netrc", ".npmrc", ".pypirc", ".env", "credentials", "kubeconfig",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
})
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore", ".tfstate", ".tfstate.backup")
SAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist")
LANGUAGES = {
    ".py": "Python", ".pyi": "Python", ".go": "Go", ".rs": "Rust",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".swift": "Swift",
    ".c": "C", ".h": "C/C++", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".cs": "C#", ".fs": "F#", ".rb": "Ruby", ".php": "PHP", ".ex": "Elixir",
    ".exs": "Elixir", ".erl": "Erlang", ".scala": "Scala", ".dart": "Dart",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell",
    ".sql": "SQL", ".tf": "HCL", ".hcl": "HCL", ".vue": "Vue",
    ".svelte": "Svelte", ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".graphql": "GraphQL", ".gql": "GraphQL", ".proto": "Protocol Buffers",
    ".r": "R", ".jl": "Julia", ".ipynb": "Jupyter", ".yaml": "YAML",
    ".yml": "YAML", ".json": "JSON", ".toml": "TOML", ".xml": "XML",
    ".md": "Markdown", ".rst": "reStructuredText",
}
MANIFESTS = frozenset({
    "package.json", "go.mod", "go.work", "cargo.toml", "pyproject.toml",
    "requirements.txt", "setup.py", "setup.cfg", "pom.xml", "build.gradle",
    "build.gradle.kts", "gemfile", "composer.json", "pubspec.yaml",
    "package.swift", "mix.exs", "deno.json", "deno.jsonc", "docker-compose.yml",
    "docker-compose.yaml", "compose.yml", "compose.yaml", "chart.yaml",
})
LOCKFILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",
    "go.sum", "cargo.lock", "poetry.lock", "uv.lock", "pipfile.lock",
    "gemfile.lock", "composer.lock", "pubspec.lock", "package.resolved", "mix.lock",
})
STAGE = re.compile(rb"^([0-7]{6}) ([0-9a-fA-F]{40,64}) [0-3]\t")


def decode(value: bytes) -> str:
    return os.fsdecode(value)


def command(args: list[str], root: Path, timeout: float, limit: int) -> dict:
    """Capture bounded stdout without a shell or unbounded communicate()."""
    env = os.environ.copy()
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat")
    output = bytearray()
    reason = None
    process = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(args, cwd=root, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "timeout"
                break
            for key, _ in selector.select(min(remaining, 0.2)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                available = limit - len(output)
                output.extend(chunk[:available])
                if len(chunk) > available:
                    reason = "output_limit"
                    break
            if reason:
                break
        if reason:
            process.kill()
        try:
            code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            reason = "timeout"
            process.kill()
            code = process.wait(timeout=2)
        return {"stdout": bytes(output), "code": code, "limit": reason}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {"stdout": bytes(output), "code": None, "limit": type(exc).__name__}
    finally:
        selector.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            if process.stdout is not None:
                process.stdout.close()


def safe_relative(value: str) -> str | None:
    path = PurePosixPath(value.rstrip("/"))
    if not value or path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    # Backslash is a legal POSIX filename; reject it only on platforms where it
    # is a path separator. A NUL can never occur in a real filename.
    if "\0" in value or (os.sep == "\\" and ("\\" in value or PureWindowsPath(value).drive)):
        return None
    return path.as_posix()


def exclusion(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if any(p in SKIP_DIRS for p in parts):
        return "dependency_build_or_vcs"
    if any(p.lower() in SENSITIVE_DIRS for p in parts):
        return "sensitive_path"
    name = parts[-1].lower()
    if name.endswith(SAMPLE_SUFFIXES):
        return None
    if (name in SENSITIVE_NAMES or name.startswith(".env.")
            or name.endswith(SENSITIVE_SUFFIXES) or name.endswith(".tfvars")
            or re.fullmatch(r"(?:secrets?|credentials?)(?:\.(?:json|ya?ml|toml|ini|txt|csv|xml|conf))?", name)
            or name.startswith("kubeconfig.")):
        return "sensitive_path"
    return None


def classify(path: str) -> tuple[str, list[str]]:
    p = PurePosixPath(path)
    name, parts = p.name.lower(), {s.lower() for s in p.parts}
    language = LANGUAGES.get(p.suffix.lower(), "Other")
    markers = []
    if name in MANIFESTS or name.endswith((".csproj", ".fsproj", ".sln")):
        markers.append("manifest")
    if name in LOCKFILES or name.endswith(".lock"):
        markers.append("lockfile")
    if name in {".nvmrc", ".node-version", ".python-version", ".tool-versions",
                ".ruby-version", "rust-toolchain", "rust-toolchain.toml", "global.json"}:
        markers.append("version_declaration")
    if name in {"agents.md", "claude.md", "contributing.md", "readme.md"}:
        markers.append("project_instructions")
    if parts & {".github", ".gitlab", ".circleci"} or name in {".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml"}:
        markers.append("ci")
    if (parts & {"deploy", "deployment", "infra", "terraform", "k8s", "kubernetes", "helm", ".devcontainer"}
            or name.startswith("dockerfile") or "compose" in name or p.suffix.lower() in {".tf", ".hcl"}):
        markers.append("deployment")
    if parts & {"test", "tests", "__tests__", "spec", "specs", "fixtures"} or re.search(r"(?:_test|\.test|\.spec)\.", name):
        markers.append("tests")
    if parts & {"migrations", "migration", "schema", "schemas", "db", "database"} or p.suffix.lower() in {".sql", ".prisma"}:
        markers.append("data")
    if parts & {"api", "routes", "handlers", "controllers", "graphql", "proto", "contracts"} or "openapi" in name:
        markers.append("interfaces")
    if parts & {"web", "frontend", "client", "ios", "android", "mobile", "components", "pages"}:
        markers.append("clients")
    if parts & {"docs", "doc", "adr", "adrs"} or p.suffix.lower() in {".md", ".rst"}:
        markers.append("documentation")
    if (parts & {"config", "configs", "configuration"} or name.startswith(".env.")
            or "config" in name or p.suffix.lower() in {".yaml", ".yml", ".toml", ".ini"}):
        markers.append("configuration")
    return language, sorted(set(markers or ["source_or_other"]))


class Inventory:
    def __init__(self, root: Path, maximum: int, depth: int):
        self.root, self.maximum, self.depth = root, maximum, depth
        self.seen: set[str] = set()
        self.files: dict[str, dict] = {}
        self.excluded: dict[str, str] = {}
        self.symlinks: set[str] = set()
        self.boundaries: dict[str, dict] = {}
        self.limitations: set[str] = set()
        self.partial = False
        self.full = False

    def gap(self, message: str) -> None:
        self.partial = True
        self.limitations.add(message)

    def admit(self, path: str) -> bool:
        if path in self.seen:
            return False
        if len(self.seen) >= self.maximum:
            self.full = True
            self.gap("Candidate-path limit reached; remaining paths were not inventoried.")
            return False
        self.seen.add(path)
        reason = exclusion(path)
        if reason:
            self.excluded[path] = reason
            return False
        return True

    def metadata(self, path: str, mode: str | None = None, oid: str | None = None,
                 origin: str = "git") -> None:
        path = safe_relative(path)
        if path is None:
            self.gap("Rejected an invalid or out-of-root candidate path.")
            return
        if not self.admit(path):
            return
        if mode == "160000":
            self.boundaries[path] = {"path": path, "kind": "git_submodule", "commit": oid}
            return
        # Check every parent before lstat: never descend into a symlink, nested
        # checkout, or excluded directory even if a tracked path names a child.
        current = self.root
        try:
            for part in PurePosixPath(path).parts[:-1]:
                current = current / part
                info = current.lstat()
                relative = current.relative_to(self.root).as_posix()
                if stat.S_ISLNK(info.st_mode):
                    self.symlinks.add(relative)
                    self.excluded[path] = "symlink_parent"
                    return
                if not stat.S_ISDIR(info.st_mode):
                    raise NotADirectoryError(relative)
                if os.path.lexists(current / ".git"):
                    self.boundaries[relative] = {"path": relative, "kind": "nested_git_repository"}
                    self.excluded[path] = "nested_git_boundary"
                    return
            target = self.root / path
            info = target.lstat()
            if stat.S_ISLNK(info.st_mode):
                self.symlinks.add(path)
            elif stat.S_ISDIR(info.st_mode):
                if os.path.lexists(target / ".git"):
                    self.boundaries[path] = {"path": path, "kind": "nested_git_repository"}
                else:
                    self.excluded[path] = "directory_candidate"
            elif stat.S_ISREG(info.st_mode):
                language, groups = classify(path)
                self.files[path] = {"path": path, "size_bytes": info.st_size,
                                    "language": language, "groups": groups, "origin": origin}
            else:
                self.excluded[path] = "special_file"
        except OSError as exc:
            self.excluded[path] = "unavailable:" + type(exc).__name__
            self.gap("Some paths disappeared or were inaccessible while collecting metadata.")

    def walk(self, start: str = "", origin: str = "filesystem") -> None:
        """Sorted, bounded traversal; inspect directory entries without following links."""
        stack = [(start, 0)]
        while stack and not self.full:
            relative, level = stack.pop()
            current = self.root / relative
            if relative:
                try:
                    info = current.lstat()
                except OSError:
                    self.gap("Some directories disappeared or were inaccessible during traversal.")
                    continue
                if stat.S_ISLNK(info.st_mode):
                    self.symlinks.add(relative)
                    continue
                if not stat.S_ISDIR(info.st_mode):
                    self.metadata(relative, origin=origin)
                    continue
                if exclusion(relative):
                    self.excluded[relative] = exclusion(relative)
                    continue
                if os.path.lexists(current / ".git"):
                    self.boundaries[relative] = {"path": relative, "kind": "nested_git_repository"}
                    continue
            if level >= self.depth:
                self.gap("Directory-depth limit reached; deeper paths were not inventoried.")
                self.excluded[relative] = "depth_limit"
                continue
            try:
                entries = []
                with os.scandir(current) as iterator:
                    for entry in iterator:
                        entries.append(entry)
                        if len(entries) > self.maximum:
                            self.gap("A directory exceeded the entry limit; its listing was truncated.")
                            break
                for entry in sorted(entries, key=lambda x: x.name):
                    path = (PurePosixPath(relative) / entry.name).as_posix()
                    if self.full:
                        break
                    if path in self.seen:
                        continue
                    reason = exclusion(path)
                    if reason:
                        self.admit(path)
                        continue
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        is_directory = False
                    if is_directory:
                        if self.admit(path):
                            stack.append((path, level + 1))
                    else:
                        self.metadata(path, origin=origin)
            except OSError:
                self.excluded[relative or "."] = "inaccessible_directory"
                self.gap("Some directories disappeared or were inaccessible during traversal.")


def git_status(data: bytes, scope: str, inventory: Inventory) -> tuple[list[dict], bool]:
    records = data.split(b"\0")
    result = []
    complete = not data or data.endswith(b"\0")
    if not complete:
        inventory.gap("Git status ended with a truncated record.")
    index = 0
    while index < len(records) - 1:
        item = records[index]
        index += 1
        if len(item) < 4 or item[2:3] != b" ":
            inventory.gap("Git status contained an incomplete or unrecognized record.")
            complete = False
            continue
        status_code, path = decode(item[:2]), decode(item[3:])
        original = None
        if "R" in status_code or "C" in status_code:
            if index >= len(records) - 1:
                inventory.gap("Git status rename record was truncated.")
                complete = False
                break
            original = decode(records[index])
            index += 1
        destination_in_scope = not scope or path.startswith(scope)
        source_in_scope = original is not None and (not scope or original.startswith(scope))
        if not destination_in_scope and not source_in_scope:
            continue
        scoped_path = path if destination_in_scope else original
        relative = scoped_path[len(scope):] if scope else scoped_path
        if safe_relative(relative) is None:
            inventory.gap("Rejected an out-of-scope Git status path.")
            complete = False
            continue
        record = {"path": relative, "status": status_code}
        if original is not None:
            record["original_git_path"] = original
        if not destination_in_scope:
            record["destination_git_path"] = path
        result.append(record)
        if len(result) >= inventory.maximum and index < len(records) - 1:
            inventory.gap("Dirty-path status reached the path limit and is incomplete.")
            complete = False
            break
    return sorted(result, key=lambda x: (x["path"], x["status"])), complete


def collect(root: Path, maximum: int, depth: int, timeout: float) -> dict:
    inventory = Inventory(root, maximum, depth)
    git = shutil.which("git")
    base = ([git, "--no-optional-locks", "-c", "core.fsmonitor=false", "-c",
             "core.untrackedCache=false", "-c", "core.quotePath=false"] if git else [])
    git_data = {"detected": False, "root": None, "commit": None, "branch": None,
                "dirty_paths": [], "status_complete": False}
    method = "filesystem"
    if git:
        top = command(base + ["rev-parse", "--show-toplevel"], root, timeout, 65536)
        if top["limit"]:
            inventory.gap("Git metadata probing failed or reached a limit; filesystem fallback may be required.")
        if top["code"] == 0 and not top["limit"]:
            top_path = Path(decode(top["stdout"].removesuffix(b"\n"))).resolve()
            try:
                prefix = root.relative_to(top_path).as_posix()
                prefix = "" if prefix == "." else prefix + "/"
            except ValueError:
                prefix = None
            if prefix is not None:
                git_data.update(detected=True, root=str(top_path))
                for name, args in (("commit", ["rev-parse", "--verify", "HEAD"]),
                                   ("branch", ["symbolic-ref", "--quiet", "--short", "HEAD"])):
                    value = command(base + args, root, timeout, 65536)
                    if value["code"] == 0 and not value["limit"]:
                        git_data[name] = decode(value["stdout"].removesuffix(b"\n"))
                limit = min(64 * 1024 * 1024, max(65536, maximum * 2048))
                listing = command(base + ["ls-files", "-z", "--cached", "--others",
                                          "--exclude-standard", "--stage", "-t"], root, timeout, limit)
                if listing["code"] == 0 or listing["stdout"]:
                    method = "git_with_relevant_metadata"
                    if listing["limit"] or listing["code"] != 0:
                        inventory.gap("Git file listing was incomplete (timeout, output cap, or command failure).")
                    for raw in listing["stdout"].split(b"\0")[:-1]:
                        if inventory.full:
                            break
                        # The type tag distinguishes untracked names from stage
                        # headers, even when a filename contains tabs/newlines
                        # and happens to look like a Git index record.
                        if raw.startswith(b"? "):
                            inventory.metadata(decode(raw[2:]))
                        else:
                            matched = STAGE.match(raw[2:]) if len(raw) > 2 else None
                            if matched:
                                inventory.metadata(decode(raw[2 + matched.end():]), decode(matched[1]), decode(matched[2]))
                            else:
                                inventory.gap("Git file listing contained an unrecognized record.")
                    for directory in RELEVANT_DIRS:
                        if os.path.lexists(root / directory) and not inventory.full:
                            inventory.walk(directory, "supplemental_metadata")
                else:
                    inventory.gap("Git file enumeration failed; used bounded filesystem traversal instead.")
                # Status may execute clean/process filters while comparing files.
                # Discover scopes and names only, never values. User-level
                # (global/system) filters such as git-lfs are the auditor's own
                # tools; decline status when any other scope defines a filter
                # (repository, worktree, include, environment) or scope is unknown.
                filters = command(base + ["config", "--null", "--show-scope", "--name-only", "--get-regexp",
                                          r"^filter\..*\.(clean|process)$"], root, timeout, 65536)
                fields = filters["stdout"].split(b"\0")
                filters_known = (filters["code"] in {0, 1} and not filters["limit"]
                                 and fields[-1] == b"" and len(fields) % 2 == 1)
                untrusted = {scope for scope in fields[:-1:2] if scope not in {b"global", b"system"}}
                if not filters_known or untrusted:
                    inventory.gap("Git dirty status was skipped because repository-scoped clean/process filters are configured or could not be ruled out; inspect those helpers before authorized execution.")
                else:
                    status_result = command(base + ["status", "--porcelain=v1", "-z",
                                                   "--untracked-files=all", "--ignore-submodules=all"],
                                            root, timeout, limit)
                    dirty_paths, status_parsed = git_status(status_result["stdout"], prefix, inventory)
                    git_data["dirty_paths"] = dirty_paths
                    git_data["status_complete"] = status_result["code"] == 0 and not status_result["limit"] and status_parsed
                    if not git_data["status_complete"]:
                        inventory.gap("Git dirty-path status was incomplete or unavailable.")
    if method == "filesystem":
        inventory.walk()
        inventory.limitations.add("Filesystem fallback does not interpret Git ignore rules.")
    else:
        inventory.limitations.add("Git-ignored paths are not enumerated except selected CI/development metadata directories.")
    inventory.limitations.update({
        "Metadata inventory is not code review, audit coverage, or proof of correctness.",
        "Source contents and symlink targets were not opened by this script; Git may internally inspect tracked files for dirty status.",
        "Stack versions and runtime configuration are unverified; filenames only identify possible evidence.",
        "Dependencies, build output, credential-like paths, nested repositories, and submodules require separate scope decisions.",
        "The filesystem may change during collection; this is not an atomic source snapshot.",
        "Filename-based groups are discovery hints, not verified architecture or ownership.",
    })
    files = [inventory.files[k] for k in sorted(inventory.files)]
    groups = collections.defaultdict(list)
    for item in files:
        for group in item["groups"]:
            groups[group].append(item["path"])
    return {
        "schema_version": 1, "root": str(root), "method": method, "git": git_data,
        "partial": inventory.partial, "limits": {"candidate_paths": maximum, "directory_depth": depth,
                                                   "git_command_timeout_seconds": timeout},
        "counts": {"candidate_paths_observed": len(inventory.seen), "files": len(files),
                   "excluded_paths_or_subtrees": len(inventory.excluded), "symlinks": len(inventory.symlinks),
                   "repository_boundaries": len(inventory.boundaries),
                   "languages": dict(sorted(collections.Counter(f["language"] for f in files).items()))},
        "files": files, "groups": dict(sorted(groups.items())),
        "excluded": [{"path": p, "reason": inventory.excluded[p]} for p in sorted(inventory.excluded)],
        "symlinks": sorted(inventory.symlinks),
        "repository_boundaries": [inventory.boundaries[p] for p in sorted(inventory.boundaries)],
        "limitations": sorted(inventory.limitations),
    }


def resolve_os_links(directory: Path) -> Path:
    """Resolve root-owned symlinks in the existing prefix of an absolute directory.

    Neither an audited repository nor a non-root process can create a root-owned
    link, so these are OS layout (macOS /tmp and /var). Every other symlink is
    left in place for the caller's no-follow check to reject.
    """
    if not hasattr(os, "geteuid") or os.geteuid() == 0:
        return directory  # as root, ownership no longer separates OS links from planted ones
    current = Path(directory.anchor)
    for index, part in enumerate(directory.parts[1:], 1):
        candidate = current / part
        try:
            info = candidate.lstat()
        except OSError:
            return candidate.joinpath(*directory.parts[index + 1:])
        current = Path(os.path.realpath(candidate)) if stat.S_ISLNK(info.st_mode) and info.st_uid == 0 else candidate
    return current


def atomic_new_output(path: str, content: str) -> None:
    """Create a new file atomically, rejecting symlink parent components.

    Root-owned OS links are resolved first. Directory descriptors pin the
    destination while writing. A hard-link publish is atomic and fails if the
    destination exists, unlike os.replace().
    """
    required = (os.open, os.mkdir, os.link, os.unlink)
    if not hasattr(os, "O_NOFOLLOW") or any(fn not in os.supports_dir_fd for fn in required):
        raise OSError("Safe atomic file output is unsupported on this platform; omit --output and use stdout.")
    destination = Path(os.path.abspath(path))
    if destination.name in {"", ".", ".."}:
        raise ValueError("Output must name a new file.")
    destination = resolve_os_links(destination.parent) / destination.name
    descriptor = os.open(destination.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = ".inventory-" + uuid.uuid4().hex + ".tmp"
    created = False
    try:
        for component in destination.parts[1:-1]:
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except FileNotFoundError:
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            except OSError as exc:
                if exc.errno not in {errno.ELOOP, errno.ENOTDIR}:
                    raise
                raise OSError(f"Output parent {component!r} is a symlink or not a directory; "
                              "choose a real directory path.") from None
            os.close(descriptor)
            descriptor = child
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=descriptor)
        created = True
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination.name, src_dir_fd=descriptor, dst_dir_fd=descriptor,
                follow_symlinks=False)
        os.fsync(descriptor)
    finally:
        if created:
            os.unlink(temporary, dir_fd=descriptor)
        os.close(descriptor)


def positive(value: str) -> int:
    number = int(value)
    if number <= 0 or number > 1_000_000:
        raise argparse.ArgumentTypeError("Use an integer from 1 to 1000000.")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Repository or source-directory scope")
    parser.add_argument("--output", help="New JSON file; existing files and symlink parents are rejected")
    parser.add_argument("--max-paths", type=positive, default=100000)
    parser.add_argument("--max-depth", type=positive, default=50)
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-Git-command timeout, 0 < seconds <= 120")
    args = parser.parse_args()
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be greater than zero and no more than 120 seconds")
    try:
        root = Path(args.root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Root must be an existing directory.")
        report = collect(root, args.max_paths, args.max_depth, args.timeout)
        content = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        if args.output:
            atomic_new_output(args.output, content)
        else:
            sys.stdout.write(content)
        return 0
    except (OSError, ValueError) as exc:
        print("inventory: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
