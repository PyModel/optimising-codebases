#!/usr/bin/env python3
"""Validate audit evidence structure and render consistent Markdown; stdlib only.

This checks internal consistency, never factual correctness or completeness.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime
import html
import heapq
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from urllib.parse import urlsplit


class Invalid(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Invalid(message)


def obj(value, where):
    need(isinstance(value, dict), f'{where}: expected object')
    return value


def string(record, key, where):
    value = record.get(key)
    need(isinstance(value, str) and bool(value.strip()), f'{where}.{key}: expected nonempty string')
    need('\x00' not in value, f'{where}.{key}: NUL is invalid')
    return value


def strings(record, key, where, nonempty=False):
    value = record.get(key)
    need(isinstance(value, list), f'{where}.{key}: expected array')
    need(not nonempty or bool(value), f'{where}.{key}: cannot be empty')
    need(all(isinstance(x, str) and x.strip() and '\x00' not in x for x in value),
         f'{where}.{key}: expected nonempty strings')
    return value


def choice(record, key, values, where):
    value = string(record, key, where)
    need(value in values, f'{where}.{key}: expected one of {", ".join(sorted(values))}')
    return value


def rows(data, key):
    value = data.get(key)
    need(isinstance(value, list), f'{key}: expected array')
    for i, row in enumerate(value):
        obj(row, f'{key}[{i}]')
    return value


def identifiers(items, where):
    result = set()
    for i, row in enumerate(items):
        name = string(row, 'id', f'{where}[{i}]')
        need(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,95}', name)), f'{where}: invalid ID {name!r}')
        need(name not in result, f'{where}: duplicate ID {name}')
        result.add(name)
    return result


def timestamp(value, where):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        raise Invalid(f'{where}: expected ISO 8601 datetime') from None
    need(result.tzinfo is not None and result.utcoffset() is not None, f'{where}: timezone required')
    return result


def references(row, key, available, where, nonempty=False):
    values = strings(row, key, where, nonempty)
    need(len(values) == len(set(values)), f'{where}.{key}: duplicate references')
    need(set(values) <= available, f'{where}.{key}: unknown references {sorted(set(values) - available)}')
    return values


def validate(data):
    obj(data, 'report')
    need(data.get('schema_version') == '1.0', 'schema_version: expected 1.0')
    audit = obj(data.get('audit'), 'audit')
    for key in ('id', 'repository', 'snapshot'):
        value = string(audit, key, 'audit')
        need('REPLACE_WITH_' not in value, f'audit.{key}: replace template values')
    start = timestamp(string(audit, 'started_at', 'audit'), 'audit.started_at')
    end = timestamp(string(audit, 'completed_at', 'audit'), 'audit.completed_at')
    need(end >= start, 'audit: completed_at precedes started_at')
    choice(audit, 'mode', {'full', 'focused', 'delta'}, 'audit')
    completion = choice(audit, 'completion', {'complete', 'partial'}, 'audit')
    choice(audit, 'working_tree', {'clean', 'dirty', 'not-git', 'unknown'}, 'audit')
    strings(audit, 'scope', 'audit', True)
    strings(audit, 'exclusions', 'audit')
    limitations = strings(audit, 'limitations', 'audit', True)
    resume = obj(data.get('resume'), 'resume')
    pending = strings(resume, 'pending_tasks', 'resume')
    strings(resume, 'notes', 'resume')
    coverage = rows(data, 'coverage')
    need(bool(coverage), 'coverage: at least one row required')
    findings = rows(data, 'findings')
    commands = rows(data, 'commands')
    sources = rows(data, 'sources')
    actions = rows(data, 'next_actions')
    adjudication = rows(data, 'adjudication')
    cov_ids = identifiers(coverage, 'coverage')
    find_ids = identifiers(findings, 'findings')
    cmd_ids = identifiers(commands, 'commands')
    source_ids = identifiers(sources, 'sources')
    action_ids = identifiers(actions, 'next_actions')
    incomplete = []
    for row in coverage:
        where = f'coverage[{row["id"]}]'
        for key in ('area', 'owner'):
            string(row, key, where)
        status = choice(row, 'status', {'reviewed', 'partial', 'blocked', 'not-reviewed', 'not-applicable'}, where)
        for key in ('paths', 'checks', 'evidence'):
            strings(row, key, where, status == 'reviewed')
        strings(row, 'gaps', where, status != 'reviewed')
        if status in {'partial', 'blocked', 'not-reviewed'}:
            incomplete.append(row['id'])
    need(completion != 'complete' or not (incomplete or pending),
         f'audit.completion: complete conflicts with incomplete coverage {incomplete} or pending tasks')
    executed = set()
    for row in commands:
        where = f'commands[{row["id"]}]'
        for key in ('command', 'environment', 'summary'):
            string(row, key, where)
        status = choice(row, 'status', {'passed', 'failed', 'blocked', 'not-run', 'inconclusive'}, where)
        need('exit_code' in row, f'{where}: exit_code required')
        code = row['exit_code']
        need(code is None or type(code) is int, f'{where}: exit_code must be integer or null')
        if status in {'passed', 'failed'}:
            need(type(code) is int, f'{where}: completed command requires exit_code')
            executed.add(row['id'])
        if status == 'passed':
            need(code == 0, f'{where}: passed command must exit zero')
        if status in {'not-run', 'blocked'}:
            need(code is None, f'{where}: unexecuted command must have null exit_code')
    for row in sources:
        where = f'sources[{row["id"]}]'
        for key in ('title', 'publisher', 'url', 'accessed_at', 'version_status', 'applies_to', 'supports'):
            string(row, key, where)
        need(not re.search(r'[\x00-\x20\x7f]', row['url']), f'{where}.url: whitespace/control characters are invalid')
        url = urlsplit(row['url'])
        need(url.scheme in {'http', 'https'} and bool(url.netloc) and not url.username and not url.password,
             f'{where}.url: expected HTTP(S) URL without credentials')
        try:
            date.fromisoformat(row['accessed_at'])
        except ValueError:
            raise Invalid(f'{where}.accessed_at: expected YYYY-MM-DD') from None
        need(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['accessed_at'])), f'{where}.accessed_at: expected YYYY-MM-DD')
    fingerprints = set()
    warnings = []
    for row in findings:
        where = f'findings[{row["id"]}]'
        for key in ('title', 'category', 'fingerprint', 'invariant', 'impact', 'recommendation', 'verification_detail'):
            string(row, key, where)
        need(row['fingerprint'] not in fingerprints, f'{where}: duplicate fingerprint; merge or distinguish root causes')
        fingerprints.add(row['fingerprint'])
        choice(row, 'kind', {'defect', 'risk', 'improvement'}, where)
        severity = choice(row, 'severity', {'critical', 'high', 'medium', 'low', 'info'}, where)
        choice(row, 'confidence', {'high', 'medium', 'low'}, where)
        verification = choice(row, 'verification', {'reproduced', 'static-verified', 'hypothesis'}, where)
        choice(row, 'priority', {'P0', 'P1', 'P2', 'P3'}, where)
        choice(row, 'effort', {'S', 'M', 'L', 'XL', 'unknown'}, where)
        for key in ('preconditions', 'failure_sequence', 'counterevidence', 'validation', 'tradeoffs'):
            strings(row, key, where, True)
        locations = rows(row, 'locations')
        need(bool(locations), f'{where}.locations: cannot be empty')
        for loc in locations:
            path = string(loc, 'path', where + '.locations')
            need(not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts
                 and not re.match(r'^[A-Za-z]:', path) and '\\' not in path,
                 f'{where}: location paths must be repository-relative with forward slashes')
            for key in ('symbol', 'observation'):
                string(loc, key, where + '.locations')
            first, last = loc.get('start_line'), loc.get('end_line')
            need(type(first) is int and type(last) is int and 1 <= first <= last,
                 f'{where}: invalid location line range')
        references(row, 'coverage_ids', cov_ids, where, True)
        refs = references(row, 'command_ids', cmd_ids, where)
        references(row, 'sources', source_ids, where)
        if verification == 'reproduced':
            need(bool(set(refs) & executed), f'{where}: reproduced requires an executed command reference')
        review = obj(row.get('independent_review'), where + '.independent_review')
        status = choice(review, 'status', {'accepted', 'revised', 'unavailable', 'not-required'}, where + '.independent_review')
        for key in ('reviewer', 'reason'):
            string(review, key, where + '.independent_review')
        if severity in {'critical', 'high'} and verification != 'hypothesis':
            need(status != 'not-required', f'{where}: consequential findings require review or explicit unavailability')
            if status == 'unavailable':
                warnings.append(f'{row["id"]}: independent review unavailable; disclose limitation')
    for row in adjudication:
        for key in ('candidate', 'reason'):
            string(row, key, 'adjudication')
        choice(row, 'decision', {'rejected', 'duplicate', 'deferred'}, 'adjudication')
        need('related_finding' in row and (row['related_finding'] is None or row['related_finding'] in find_ids),
             'adjudication: related_finding must be null or an existing finding ID')
        if row['decision'] == 'duplicate':
            need(row['related_finding'] is not None, 'adjudication: duplicate must reference retained finding')
    graph = {}
    for row in actions:
        where = f'next_actions[{row["id"]}]'
        for key in ('action', 'acceptance'):
            string(row, key, where)
        choice(row, 'priority', {'P0', 'P1', 'P2', 'P3'}, where)
        references(row, 'finding_ids', find_ids, where)
        graph[row['id']] = set(references(row, 'depends_on', action_ids, where))
    done = set()
    while graph:
        ready = {key for key, deps in graph.items() if deps <= done}
        need(bool(ready), 'next_actions: cyclic dependencies')
        done.update(ready)
        graph = {key: deps for key, deps in graph.items() if key not in ready}
    if not sources:
        warnings.append('No online sources recorded; explain whether unavailable or unnecessary for the chosen scope.')
    if incomplete:
        warnings.append('Partial coverage: ' + ', '.join(incomplete))
    return warnings


def clean(value):
    value = html.escape(str(value), quote=False).replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'([\\`*_\[\]!#|])', r'\\\1', value)


def bullets(values):
    return ['- ' + clean(x) for x in values] or ['- None recorded.']


def ordered_actions(actions):
    """Topologically order actions; prioritize only among ready actions."""
    by_id = {item['id']: item for item in actions}
    remaining = {item['id']: len(item['depends_on']) for item in actions}
    dependents = {key: [] for key in by_id}
    for item in actions:
        for dependency in item['depends_on']:
            dependents[dependency].append(item['id'])
    ready = [(by_id[key]['priority'], key) for key, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _, key = heapq.heappop(ready)
        ordered.append(by_id[key])
        for child in dependents[key]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, (by_id[child]['priority'], child))
    need(len(ordered) == len(actions), 'next_actions: cyclic dependencies')
    return ordered


def render(data):
    audit = data['audit']
    findings = data['findings']
    verified = [f for f in findings if f['kind'] == 'defect' and f['verification'] != 'hypothesis']
    risks = [f for f in findings if f['kind'] == 'risk' and f['verification'] != 'hypothesis']
    improvements = [f for f in findings if f['kind'] == 'improvement' and f['verification'] != 'hypothesis']
    hypotheses = [f for f in findings if f['verification'] == 'hypothesis']
    counts = Counter(f['severity'] for f in verified)
    out = ['# Codebase audit: ' + clean(audit['repository']), '',
           '**Snapshot:** ' + clean(audit['snapshot']), '',
           '**Review:** ' + clean(audit['mode']) + ' / ' + clean(audit['completion']), '',
           '**Completed:** ' + clean(audit['completed_at']), '',
           '## Scope and evidence boundary', '',
           '**Included:** ' + '; '.join(clean(x) for x in audit['scope']), '',
           '**Excluded:** ' + ('; '.join(clean(x) for x in audit['exclusions']) or 'None declared.'), '',
           *bullets(audit['limitations']), '', '## Counts', '',
           f'Verified defects: **{len(verified)}**; substantiated risks: **{len(risks)}**; hypotheses: **{len(hypotheses)}**; substantiated improvements: **{len(improvements)}**.', '',
           'Severity counts below include verified defects only.', '',
           '| Critical | High | Medium | Low | Info |', '|---:|---:|---:|---:|---:|',
           '| ' + ' | '.join(str(counts[x]) for x in ('critical', 'high', 'medium', 'low', 'info')) + ' |', '',
           'Completed coverage does not establish that no defects remain.', '', '## Remediation and verification order', '']
    for action in ordered_actions(data['next_actions']):
        out += [f'### {clean(action["id"])} · {clean(action["priority"])}', '', clean(action['action']), '',
                '**Finding references:** ' + (', '.join(action['finding_ids']) or 'Coverage/verification task'), '',
                '**Prerequisites:** ' + (', '.join(action['depends_on']) or 'None declared'), '',
                '**Acceptance:** ' + clean(action['acceptance']), '']
    if not data['next_actions']:
        out += ['No actions recorded.', '']
    for heading, group in [('Verified defects', verified), ('Substantiated future risks', risks),
                           ('Hypotheses requiring verification', hypotheses), ('Optional improvements', improvements)]:
        out += ['## ' + heading, '']
        if not group:
            out += ['None established within the reviewed scope.', '']
        for item in sorted(group, key=lambda x: (x['priority'], x['id'])):
            out += [f'### {clean(item["id"])} — {clean(item["title"])}', '',
                    ' · '.join('**' + label + ':** ' + clean(item[key]) for label, key in [('Kind', 'kind'), ('Category', 'category'), ('Severity', 'severity'), ('Confidence', 'confidence'), ('Verification', 'verification'), ('Priority', 'priority')]),
                    '', '**Invariant:** ' + clean(item['invariant']), '', '**Evidence:**', '']
            for loc in item['locations']:
                out += [f'- {clean(loc["path"])}:{loc["start_line"]}–{loc["end_line"]} ({clean(loc["symbol"])}): {clean(loc["observation"])}']
            for title, key in [('Preconditions', 'preconditions'), ('Failure / benefit mechanism', 'failure_sequence'),
                               ('Controls and counterevidence checked', 'counterevidence')]:
                out += ['', '**' + title + ':**', '', *bullets(item[key])]
            out += ['', '**Impact:** ' + clean(item['impact']), '',
                    '**Verification:** ' + clean(item['verification_detail']), '',
                    '**Executed command references:** ' + (', '.join(item['command_ids']) or 'None; see verification classification'), '',
                    '**Recommendation:** ' + clean(item['recommendation']), '',
                    '**Effort:** ' + clean(item['effort']), '', '**Trade-offs:**', '', *bullets(item['tradeoffs']), '',
                    '**Acceptance checks:**', '', *bullets(item['validation']), '',
                    '**Independent review:** ' + '; '.join(clean(item['independent_review'][k]) for k in ('status', 'reviewer', 'reason')), '',
                    '**Source references:** ' + (', '.join(item['sources']) or 'Local source evidence'), '',
                    '**Coverage references:** ' + ', '.join(item['coverage_ids']), '']
    out += ['## Coverage ledger', '', '| ID | Area | Owner | Status |', '|---|---|---|---|']
    for row in data['coverage']:
        out += ['| ' + ' | '.join(clean(row[k]) for k in ('id', 'area', 'owner', 'status')) + ' |']
    for row in data['coverage']:
        out += ['', '### ' + clean(row['id']) + ' · ' + clean(row['area']), '']
        for heading, key in [('Paths', 'paths'), ('Checks', 'checks'), ('Evidence', 'evidence'), ('Gaps / non-applicability', 'gaps')]:
            out += ['**' + heading + ':**', '', *bullets(row[key]), '']
    out += ['## Verification ledger', '']
    for row in data['commands']:
        out += ['### ' + clean(row['id']) + ' · ' + clean(row['status']), '',
                '**Command:** ' + clean(row['command']), '', '**Environment:** ' + clean(row['environment']), '',
                '**Exit:** ' + clean(row['exit_code']), '', clean(row['summary']), '']
    out += ['## Source ledger', '']
    for row in data['sources']:
        url = row['url'].replace(' ', '%20').replace('(', '%28').replace(')', '%29')
        title = clean(row['title'])
        out += [f'### {clean(row["id"])} · [{title}]({url})', '',
                f'{clean(row["publisher"])}; accessed {clean(row["accessed_at"])}; {clean(row["version_status"])}.', '',
                '**Supports:** ' + clean(row['supports']), '', '**Applicability:** ' + clean(row['applies_to']), '']
    out += ['## Candidate adjudication', '']
    for row in data['adjudication']:
        out += ['- ' + clean(row['candidate']) + ': ' + clean(row['decision']) + ' — ' + clean(row['reason'])
                + ('; retained as ' + clean(row['related_finding']) if row['related_finding'] else '')]
    out += ['', '## Remaining work', '', *bullets(data['resume']['pending_tasks']), '', *bullets(data['resume']['notes']), '']
    return '\n'.join(out)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise Invalid('non-finite JSON number: ' + value)


def write_atomic(path, content, source):
    need(path.suffix.lower() == '.md', '--render destination must use .md')
    need(path.resolve() != source.resolve(), 'render destination cannot overwrite input')
    need(not path.is_symlink(), 'render destination cannot be a symlink')
    need(not any(parent.is_symlink() for parent in path.absolute().parents), 'render parent cannot be a symlink')
    need(not path.exists() or path.is_file(), 'render destination must be a regular file')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.audit-report-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--render', type=Path, help='Write Markdown only after successful validation')
    args = parser.parse_args()
    try:
        need(args.report.is_file(), 'report must be a regular file')
        need(args.report.stat().st_size <= 32 * 1024 * 1024, 'report exceeds 32 MiB; split audit into scoped reports')
        data = json.loads(args.report.read_text(encoding='utf-8'), object_pairs_hook=unique_object, parse_constant=reject_constant)
        warnings = validate(data)
        if args.render:
            write_atomic(args.render, render(data), args.report)
        print(f'Valid audit: {len(data["findings"])} items, {len(data["coverage"])} coverage rows.')
        for warning in warnings:
            print('Warning: ' + warning)
        print('Structural validation only; evidence truth and actual coverage require review.')
        return 0
    except (Invalid, OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print('Invalid audit: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
