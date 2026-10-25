#!/usr/bin/env python3
"""Read-only Java @Tool inventory; optional comparison with saved MCP tools/list.

This helper never connects to ZAP, executes a tool, reads credentials, or claims
runtime readiness. It reads Java sources and an optional caller-selected listing.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re


TOKEN = re.compile(r'"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/')


def mask_java(source):
    return TOKEN.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m.group()), source)


def parameter_names(signature):
    """Extract top-level Java argument names, without claiming JSON type equivalence."""
    text = mask_java(signature)
    # Remove parameter annotations with balanced parentheses (descriptions are masked).
    pattern = re.compile(r'@\w+(?:\.\w+)*')
    while match := pattern.search(text):
        end = match.end()
        while end < len(text) and text[end].isspace():
            end += 1
        if end < len(text) and text[end] == '(':
            depth = 1
            end += 1
            while end < len(text) and depth:
                depth += (text[end] == '(') - (text[end] == ')')
                end += 1
            if depth:
                raise ValueError('unterminated parameter annotation')
        text = text[:match.start()] + ' ' + text[end:]
    start, end = text.find('('), text.rfind(')')
    if start < 0 or end < start:
        raise ValueError('method parameters not recognized')
    args = text[start+1:end].strip()
    if not args:
        return []
    parts, begin, depth = [], 0, 0
    for i, char in enumerate(args):
        if char in '<[':
            depth += 1
        elif char in '>]':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(args[begin:i]); begin = i+1
    parts.append(args[begin:])
    names = []
    for part in parts:
        match = re.search(r'\b([A-Za-z_$][\w$]*)\s*(?:\[\s*\]\s*)*$', part)
        if not match:
            raise ValueError('parameter name not recognized')
        names.append(match.group(1))
    return names


def string_value(expression):
    values = []
    remainder = TOKEN.sub('', expression).replace('+', '').strip()
    if remainder:
        raise ValueError('annotation string uses a nonliteral expression; inspect source manually')
    for match in TOKEN.finditer(expression):
        token = match.group()
        if token.startswith(('//', '/*')):
            continue
        if token.startswith('"""'):
            values.append(' '.join(token[3:-3].split()))
        else:
            values.append(json.loads(token))
    return ''.join(values)


def parse_tools(source, source_path):
    masked = mask_java(source)
    tools = []
    for match in re.finditer(r'@Tool\s*\(', masked):
        begin = match.end()
        end = begin
        depth = 1
        while end < len(masked) and depth:
            if masked[end] == '(':
                depth += 1
            elif masked[end] == ')':
                depth -= 1
            end += 1
        if depth:
            raise ValueError('unterminated @Tool annotation')
        annotation = source[begin:end-1]
        # Split only outside strings/comments/nested syntax, not commas in descriptions.
        am = mask_java(annotation)
        fields = []
        start = 0
        nesting = 0
        for i, c in enumerate(am):
            if c in '({[':
                nesting += 1
            elif c in ')}]':
                nesting -= 1
            elif c == ',' and nesting == 0:
                fields.append(annotation[start:i]); start = i+1
        fields.append(annotation[start:])
        attrs = {}
        for field in fields:
            if '=' in field:
                key, value = field.split('=', 1)
                attrs[key.strip()] = value.strip()
        if 'name' not in attrs or 'description' not in attrs:
            raise ValueError('tool without explicit name/description; inspect source manually')
        declaration = re.match(r'\s*public\s+([^\{;]+)\{', masked[end:])
        if not declaration:
            raise ValueError('tool method declaration not recognized')
        signature = source[end:end+declaration.end()-1].strip()
        tools.append({'name': string_value(attrs['name']),
                      'description': string_value(attrs['description']),
                      'source': str(source_path), 'line': source.count('\n', 0, match.start())+1,
                      'methodDeclaration': signature,
                      'sourceParameterNames': parameter_names(signature),
                      'surface': 'expert' if re.search(r'implements\s+[^\{;]*\bExpertToolGroup\b', masked) else 'base'})
    return tools


def inventory(repo):
    source_root = repo/'src/main/java'
    if not source_root.is_dir():
        raise ValueError('repo must contain src/main/java')
    rows = []
    for path in sorted(source_root.rglob('*.java')):
        rows.extend(parse_tools(path.read_text(), path.relative_to(repo)))
    names = [row['name'] for row in rows]
    if not names or len(names) != len(set(names)):
        raise ValueError('empty or duplicate tool inventory')
    return rows


def runtime_names(value):
    if isinstance(value, dict) and isinstance(value.get('result'), dict):
        value = value['result']
    if not isinstance(value, dict) or not isinstance(value.get('tools'), list):
        raise ValueError('runtime input must be a tools/list result or JSON-RPC envelope')
    if value.get('nextCursor'):
        raise ValueError('runtime listing is paginated; combine all pages before comparison')
    names = [row.get('name') for row in value['tools'] if isinstance(row, dict)]
    if len(names) != len(value['tools']) or any(not isinstance(n, str) or not n for n in names):
        raise ValueError('invalid runtime tool name')
    if len(names) != len(set(names)):
        raise ValueError('duplicate runtime tool name')
    return set(names)


def compare_runtime(rows, value):
    actual = runtime_names(value)
    listing = value['result'] if isinstance(value.get('result'), dict) else value
    native = {row['name']: row for row in listing['tools']}
    source = {row['name']: row for row in rows}
    differences = []
    for name in sorted(actual & source.keys()):
        schema = native[name].get('inputSchema')
        if not isinstance(schema, dict) or not isinstance(schema.get('properties'), dict):
            differences.append({'name': name, 'comparison': 'not-comparable',
                                'reason': 'object properties unavailable; inspect schema'})
            continue
        declared = set(source[name]['sourceParameterNames'])
        exposed = set(schema['properties'])
        if declared != exposed:
            differences.append({'name': name, 'comparison': 'parameter-name-drift',
                                'sourceParametersAbsentFromRuntime': sorted(declared-exposed),
                                'runtimePropertiesAbsentFromSource': sorted(exposed-declared),
                                'runtimeAdditionalProperties': schema.get('additionalProperties', 'unspecified')})
    return {'sourceNotExposed': sorted(source.keys()-actual),
            'runtimeNotInSource': sorted(actual-source.keys()),
            'matched': sorted(actual & source.keys()),
            'parameterComparisons': differences,
            'meaning': 'registration and parameter-name comparison only; not type/requiredness/auth semantics, execution, or readiness; drift does not identify which revision is correct'}



def compare_runtime_pair(left, right):
    """Actual deployment comparison, separate from source name-only comparison."""
    ln, rn = runtime_names(left), runtime_names(right)
    def tools(value):
        value = value['result'] if isinstance(value.get('result'), dict) else value
        return {t['name']: t for t in value['tools']}
    a, b = tools(left), tools(right)
    rows = []
    for name in sorted(ln & rn):
        x, y = a[name].get('inputSchema'), b[name].get('inputSchema')
        if not isinstance(x, dict) or not isinstance(y, dict):
            rows.append({'name': name, 'comparison': 'not-comparable'}); continue
        px, py = x.get('properties', {}), y.get('properties', {})
        if not isinstance(px, dict) or not isinstance(py, dict):
            rows.append({'name': name, 'comparison': 'not-comparable'}); continue
        rows.append({'name': name, 'leftRequired': x.get('required', []), 'rightRequired': y.get('required', []),
            'leftAdditionalProperties': x.get('additionalProperties', 'unspecified'),
            'rightAdditionalProperties': y.get('additionalProperties', 'unspecified'),
            'fieldsOnlyLeft': sorted(px.keys()-py.keys()), 'fieldsOnlyRight': sorted(py.keys()-px.keys()),
            'fieldContracts': [{'field': n, 'leftRequired': n in x.get('required', []),
                'rightRequired': n in y.get('required', []), 'left': px.get(n), 'right': py.get(n)}
                for n in sorted(px.keys() | py.keys())],
            'sameInputSchema': x == y,
            'leftDescription': a[name].get('description'), 'rightDescription': b[name].get('description')})
    return {'onlyLeft': sorted(ln-rn), 'onlyRight': sorted(rn-ln), 'tools': rows,
        'meaning': 'Saved actual schemas, requiredness, types and constraints; descriptions aid manual auth review but do not prove configured kind/session/semantics or execution.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--runtime-tools', type=Path, help='Saved full MCP tools/list JSON; optional, never fetched')
    parser.add_argument('--candidate-tools', type=Path, help='Saved full candidate tools/list; compare actual schemas with --runtime-tools')
    parser.add_argument('--routing', type=Path, help='Routing Markdown to check for every exact source tool name')
    args = parser.parse_args(argv)
    try:
        if args.candidate_tools and not args.runtime_tools:
            raise ValueError('candidate comparison requires runtime tools')
        rows = inventory(args.repo.resolve())
        names = {row['name'] for row in rows}
        result = {'kind': 'source-inventory', 'toolCount': len(rows), 'tools': rows,
                  'runtimeReadiness': 'not-tested', 'executedOperations': 0}
        missing = []
        if args.routing:
            text = args.routing.read_text()
            documented = set(re.findall(r'\bzap_[a-z0-9_]+\b', text))
            missing = sorted(names-documented)
            stale = sorted(documented-names)
            result['routingCheck'] = {'undocumentedTools': missing, 'unknownToolNames': stale,
                                      'meaning': 'name coverage only; agent must inspect semantics and gates'}
            missing += stale
        if args.runtime_tools:
            result['runtimeComparison'] = compare_runtime(rows, json.loads(args.runtime_tools.read_text()))
        if args.candidate_tools:
            result['deploymentComparison'] = compare_runtime_pair(json.loads(args.runtime_tools.read_text()), json.loads(args.candidate_tools.read_text()))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if missing else 0
    except (OSError, ValueError) as error:
        # Never echo file contents, profile values, or supplied listing payloads.
        print(json.dumps({'error': type(error).__name__, 'message': 'Inventory failed; inspect source/listing format and selected paths', 'executedOperations': 0}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
