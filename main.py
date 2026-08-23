import os
import sys
import re
import shutil
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    '.py': 'Python', '.js': 'JavaScript', '.mjs': 'JavaScript', '.cjs': 'JavaScript',
    '.jsx': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript', '.html': 'HTML',
    '.htm': 'HTML', '.css': 'CSS', '.scss': 'SCSS', '.sass': 'Sass', '.less': 'Less',
    '.php': 'PHP', '.java': 'Java', '.c': 'C', '.h': 'C/C++ Header', '.cpp': 'C++',
    '.hpp': 'C++ Header', '.cs': 'C#', '.rb': 'Ruby', '.go': 'Go', '.rs': 'Rust',
    '.swift': 'Swift', '.kt': 'Kotlin', '.kts': 'Kotlin', '.sql': 'SQL', '.sh': 'Shell',
    '.bash': 'Shell', '.zsh': 'Shell', '.ps1': 'PowerShell', '.bat': 'Batch',
    '.cmd': 'Batch', '.xml': 'XML', '.json': 'JSON', '.yaml': 'YAML', '.yml': 'YAML',
    '.toml': 'TOML', '.ini': 'INI', '.cfg': 'Config', '.md': 'Markdown',
    '.rst': 'reStructuredText', '.tex': 'LaTeX', '.r': 'R', '.pl': 'Perl', '.lua': 'Lua'
}

COMMENT_MARKERS = {
    'Python': {'single': ['#'], 'multi_start': ['"""', "'''"], 'multi_end': ['"""', "'''"]},
    'JavaScript': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'TypeScript': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'HTML': {'single': [], 'multi_start': ['<!--'], 'multi_end': ['-->']},
    'CSS': {'single': [], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'SCSS': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Sass': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Less': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'PHP': {'single': ['//', '#'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Java': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'C': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'C++': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'C#': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Ruby': {'single': ['#'], 'multi_start': ['=begin'], 'multi_end': ['=end']},
    'Go': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Rust': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Swift': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Kotlin': {'single': ['//'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'SQL': {'single': ['--'], 'multi_start': ['/*'], 'multi_end': ['*/']},
    'Shell': {'single': ['#'], 'multi_start': [], 'multi_end': []},
    'PowerShell': {'single': ['#'], 'multi_start': ['<#'], 'multi_end': ['#>']},
    'Batch': {'single': ['REM', '::'], 'multi_start': [], 'multi_end': []},
    'XML': {'single': [], 'multi_start': ['<!--'], 'multi_end': ['-->']},
    'YAML': {'single': ['#'], 'multi_start': [], 'multi_end': []},
    'TOML': {'single': ['#'], 'multi_start': [], 'multi_end': []},
    'INI': {'single': [';', '#'], 'multi_start': [], 'multi_end': []},
    'Markdown': {'single': [], 'multi_start': ['<!--'], 'multi_end': ['-->']},
    'LaTeX': {'single': ['%'], 'multi_start': [], 'multi_end': []},
    'Perl': {'single': ['#'], 'multi_start': [], 'multi_end': []},
    'Lua': {'single': ['--'], 'multi_start': ['--[['], 'multi_end': [']]']}
}

FUNCTION_CLASS_PATTERNS = {
    'Python': {'function': re.compile(r'^\s*def\s+(\w+)\s*\('), 'class': re.compile(r'^\s*class\s+(\w+)\s*[:\(]')},
    'PHP': {'function': re.compile(r'^\s*(?:public\s+|private\s+|protected\s+|static\s+)*function\s+(\w+)\s*\('),
            'class': re.compile(r'^\s*(?:abstract\s+|final\s+)*class\s+(\w+)')},
    'JavaScript': {'function': re.compile(r'\bfunction\s+(\w+)\s*\(|\b(\w+)\s*=\s*(?:async\s*)?function\s*\('),
                   'class': re.compile(r'\bclass\s+(\w+)')},
    'TypeScript': {'function': re.compile(r'\bfunction\s+(\w+)\s*\(|\b(\w+)\s*=\s*(?:async\s*)?function\s*\('),
                   'class': re.compile(r'\bclass\s+(\w+)')},
    'Java': {'function': re.compile(r'^\s*(?:public|private|protected|static|final|synchronized|native|abstract)*\s+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{'),
             'class': re.compile(r'^\s*(?:public|private|protected|static|final|abstract)*\s*class\s+(\w+)')},
    'C': {'function': re.compile(r'^\s*[\w\s\*]+?\s+(\w+)\s*\([^;]*?\)\s*\{'), 'class': None},
    'C++': {'function': re.compile(r'^\s*(?:[\w:]+[\s\*&]+)+(\w+)\s*\([^;]*?\)\s*(?:const\s*)?\{'),
            'class': re.compile(r'^\s*(?:class|struct)\s+(\w+)')},
    'C#': {'function': re.compile(r'^\s*(?:public|private|protected|internal|static|virtual|override|async|sealed|abstract)*\s+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*\{'),
           'class': re.compile(r'^\s*(?:public|private|protected|internal|static|sealed|abstract)*\s*class\s+(\w+)')},
    'Ruby': {'function': re.compile(r'^\s*def\s+(\w+)'), 'class': re.compile(r'^\s*class\s+(\w+)')},
    'Go': {'function': re.compile(r'^\s*func\s+(?:\([^)]*\)\s+)?(\w+)\s*\('), 'class': None},
    'Rust': {'function': re.compile(r'^\s*fn\s+(\w+)\s*\('), 'class': re.compile(r'^\s*(?:struct|enum|trait)\s+(\w+)')},
    'Swift': {'function': re.compile(r'^\s*func\s+(\w+)\s*\('), 'class': re.compile(r'^\s*class\s+(\w+)')},
    'Kotlin': {'function': re.compile(r'^\s*fun\s+(\w+)\s*\('), 'class': re.compile(r'^\s*class\s+(\w+)')},
    'Lua': {'function': re.compile(r'^\s*function\s+(\w+)\s*\('), 'class': None}
}


def get_language(file_path):
    return SUPPORTED_EXTENSIONS.get(file_path.suffix.lower())


def remove_comments_from_text(text, language):
    markers = COMMENT_MARKERS.get(language)
    if not markers:
        return text
    lines = text.splitlines(True)
    out = []
    in_multi = False
    multi_end = None
    for line in lines:
        if in_multi:
            idx = line.find(multi_end)
            if idx != -1:
                out.append(line[idx + len(multi_end):])
                in_multi = False
                multi_end = None
            continue
        stripped = line.lstrip()
        matched = False
        for marker in markers['single']:
            if stripped.startswith(marker):
                out.append('\n' if line.endswith('\n') else '')
                matched = True
                break
        if matched:
            continue
        for i, start in enumerate(markers['multi_start']):
            idx = line.find(start)
            if idx != -1:
                end = markers['multi_end'][i]
                end_idx = line.find(end, idx + len(start))
                if end_idx != -1:
                    out.append(line[:idx] + line[end_idx + len(end):])
                else:
                    out.append(
                        line[:idx] + '\n' if line.endswith('\n') else line[:idx])
                    in_multi = True
                    multi_end = end
                matched = True
                break
        if not matched:
            out.append(line)
    return ''.join(out)


def analyze_file(file_path):
    lang = get_language(file_path)
    if not lang:
        return None
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None

    start_time = time.time()
    lines = content.splitlines()
    total_lines = len(lines)
    total_characters = len(content)

    blank_lines = 0
    code_lines = 0
    single_comment_lines = 0
    multi_comment_lines = 0
    mixed_lines = 0

    markers = COMMENT_MARKERS.get(lang, {})
    single_markers = markers.get('single', [])
    multi_start = markers.get('multi_start', [])
    multi_end = markers.get('multi_end', [])

    in_multi = False
    current_multi_end = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_lines += 1
            continue

        if in_multi:
            multi_comment_lines += 1
            if current_multi_end and current_multi_end in line:
                in_multi = False
                current_multi_end = None
            continue

        is_single_comment = False
        for marker in single_markers:
            if stripped.startswith(marker):
                single_comment_lines += 1
                is_single_comment = True
                break
        if is_single_comment:
            continue

        has_multi_start = False
        for i, start_marker in enumerate(multi_start):
            idx = line.find(start_marker)
            if idx != -1:
                has_multi_start = True
                end_marker = multi_end[i] if i < len(multi_end) else None
                if end_marker and end_marker in line[idx + len(start_marker):]:
                    mixed_lines += 1
                else:
                    mixed_lines += 1
                    in_multi = True
                    current_multi_end = end_marker
                break
        if has_multi_start:
            continue

        code_lines += 1

    functions = 0
    classes = 0
    if lang in FUNCTION_CLASS_PATTERNS:
        pats = FUNCTION_CLASS_PATTERNS[lang]
        if pats.get('function'):
            functions = len(pats['function'].findall(content))
        if pats.get('class'):
            classes = len(pats['class'].findall(content))

    stripped_lines = [line.strip() for line in lines if line.strip()]
    line_counts = Counter(stripped_lines)
    duplicate_lines = sum(
        count - 1 for count in line_counts.values() if count > 1)

    line_lengths = [len(line) for line in lines if line.strip()]
    if line_lengths:
        longest_line = max(line_lengths)
        shortest_line = min(line_lengths)
        avg_line_length = sum(line_lengths) / len(line_lengths)
    else:
        longest_line = 0
        shortest_line = 0
        avg_line_length = 0

    buckets = {'0-20': 0, '21-40': 0, '41-60': 0,
               '61-80': 0, '81-100': 0, '100+': 0}
    for ll in line_lengths:
        if ll <= 20:
            buckets['0-20'] += 1
        elif ll <= 40:
            buckets['21-40'] += 1
        elif ll <= 60:
            buckets['41-60'] += 1
        elif ll <= 80:
            buckets['61-80'] += 1
        elif ll <= 100:
            buckets['81-100'] += 1
        else:
            buckets['100+'] += 1

    return {
        'path': str(file_path),
        'name': file_path.name,
        'language': lang,
        'total_lines': total_lines,
        'blank_lines': blank_lines,
        'code_lines': code_lines,
        'comment_lines': single_comment_lines + multi_comment_lines,
        'single_comments': single_comment_lines,
        'multi_comments': multi_comment_lines,
        'mixed_lines': mixed_lines,
        'total_characters': total_characters,
        'longest_line': longest_line,
        'shortest_line': shortest_line,
        'avg_line_length': round(avg_line_length, 2),
        'length_buckets': buckets,
        'functions': functions,
        'classes': classes,
        'duplicate_lines': duplicate_lines,
        'size_bytes': file_path.stat().st_size,
        'has_comments': single_comment_lines + multi_comment_lines > 0,
        'analysis_time': time.time() - start_time
    }


def collect_files(project_path):
    if project_path.is_file():
        return [project_path] if get_language(project_path) else []
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(project_path.rglob(f'*{ext}'))
        files.extend(project_path.rglob(f'*{ext.upper()}'))
    filtered = []
    for f in files:
        if any(part in ('node_modules', '.git', '__pycache__', 'venv', 'env') for part in f.parts):
            continue
        filtered.append(f)
    return list(set(filtered))


def aggregate_stats(results):
    if not results:
        return {}
    total_files = len(results)
    total_lines = sum(r['total_lines'] for r in results)
    total_blank = sum(r['blank_lines'] for r in results)
    total_code = sum(r['code_lines'] for r in results)
    total_comment = sum(r['comment_lines'] for r in results)
    total_mixed = sum(r['mixed_lines'] for r in results)
    total_single = sum(r['single_comments'] for r in results)
    total_multi = sum(r['multi_comments'] for r in results)
    total_chars = sum(r['total_characters'] for r in results)
    total_dup = sum(r['duplicate_lines'] for r in results)
    total_func = sum(r['functions'] for r in results)
    total_class = sum(r['classes'] for r in results)

    lang_stats = defaultdict(lambda: {'files': 0, 'lines': 0, 'code_lines': 0, 'blank_lines': 0,
                                      'comment_lines': 0, 'mixed_lines': 0, 'single_comments': 0,
                                      'multi_comments': 0, 'characters': 0, 'functions': 0, 'classes': 0})
    for r in results:
        s = lang_stats[r['language']]
        s['files'] += 1
        s['lines'] += r['total_lines']
        s['code_lines'] += r['code_lines']
        s['blank_lines'] += r['blank_lines']
        s['comment_lines'] += r['comment_lines']
        s['mixed_lines'] += r['mixed_lines']
        s['single_comments'] += r['single_comments']
        s['multi_comments'] += r['multi_comments']
        s['characters'] += r['total_characters']
        s['functions'] += r['functions']
        s['classes'] += r['classes']

    for lang, s in lang_stats.items():
        s['percentage_lines'] = round(
            (s['lines'] / total_lines) * 100, 2) if total_lines else 0
        s['percentage_files'] = round(
            (s['files'] / total_files) * 100, 2) if total_files else 0
        s['comment_ratio'] = round(
            (s['comment_lines'] / s['lines']) * 100, 2) if s['lines'] else 0

    largest_by_lines = max(results, key=lambda x: x['total_lines'])
    smallest_by_lines = min(results, key=lambda x: x['total_lines'])
    largest_by_size = max(results, key=lambda x: x['size_bytes'])
    files_over_500 = [r for r in results if r['total_lines'] > 500]
    empty_files = [r for r in results if r['total_lines']
                   == 0 or r['total_lines'] == r['blank_lines']]
    files_no_comments = [r for r in results if not r['has_comments']]
    files_most_comments = sorted(
        results, key=lambda x: x['comment_lines'], reverse=True)[:10]

    all_lengths = []
    for r in results:
        if r['total_lines'] > 0:
            all_lengths.append(r['avg_line_length'] * r['total_lines'])
    overall_avg_len = sum(
        all_lengths) / sum(r['total_lines'] for r in results) if results else 0
    longest_line = max(r['longest_line'] for r in results)
    shortest_line = min(r['shortest_line'] for r in results) if any(
        r['shortest_line'] > 0 for r in results) else 0

    total_analysis_time = sum(r['analysis_time'] for r in results)
    slowest = max(results, key=lambda x: x['analysis_time'])
    fastest = min(results, key=lambda x: x['analysis_time'])

    buckets = defaultdict(int)
    for r in results:
        for b, c in r['length_buckets'].items():
            buckets[b] += c

    return {
        'total_files': total_files,
        'total_lines': total_lines,
        'total_blank_lines': total_blank,
        'total_code_lines': total_code,
        'total_comment_lines': total_comment,
        'total_mixed_lines': total_mixed,
        'total_single_comments': total_single,
        'total_multi_comments': total_multi,
        'total_characters': total_chars,
        'total_duplicate_lines': total_dup,
        'duplicate_line_ratio': round((total_dup / total_lines) * 100, 2) if total_lines else 0,
        'total_functions': total_func,
        'total_classes': total_class,
        'overall_comment_ratio': round((total_comment / total_lines) * 100, 2) if total_lines else 0,
        'avg_comments_per_file': round(total_comment / total_files, 2) if total_files else 0,
        'overall_avg_line_length': round(overall_avg_len, 2),
        'longest_line': longest_line,
        'shortest_line': shortest_line,
        'language_stats': dict(lang_stats),
        'largest_file_by_lines': largest_by_lines,
        'smallest_file_by_lines': smallest_by_lines,
        'largest_file_by_size': largest_by_size,
        'files_over_500': files_over_500,
        'empty_files': empty_files,
        'files_without_comments': files_no_comments,
        'files_with_most_comments': files_most_comments,
        'total_analysis_time': total_analysis_time,
        'slowest_file': slowest,
        'fastest_file': fastest,
        'line_length_buckets': dict(buckets)
    }


def generate_html_report(project_name, stats, output_path):
    template_path = Path(__file__).parent / 'rep_temp.html'
    try:
        template = template_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        template = DEFAULT_TEMPLATE
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lang_rows = ''
    for lang, data in sorted(stats['language_stats'].items(), key=lambda x: x[1]['percentage_lines'], reverse=True):
        lang_rows += f"""
        <tr>
            <td>{lang}</td>
            <td>{data['files']}</td>
            <td>{data['lines']}</td>
            <td>{data['code_lines']}</td>
            <td>{data['blank_lines']}</td>
            <td>{data['comment_lines']}</td>
            <td>{data['mixed_lines']}</td>
            <td>{data['characters']}</td>
            <td>{data['percentage_lines']}%</td>
            <td>{data['comment_ratio']}%</td>
            <td><div class="bar" style="width:{data['percentage_lines']}%"></div></td>
        </tr>"""
    buckets_rows = ''
    for b in ['0-20', '21-40', '41-60', '61-80', '81-100', '100+']:
        buckets_rows += f'<tr><td>{b}</td><td>{stats["line_length_buckets"].get(b, 0)}</td></tr>'

    def list_files(files):
        if not files:
            return '<p>None</p>'
        items = ''
        for f in files[:10]:
            items += f'<li>{f["path"]} ({f["language"]}, {f["total_lines"]} lines, {f["size_bytes"]} bytes)</li>'
        if len(files) > 10:
            items += f'<li>... and {len(files)-10} more</li>'
        return f'<ul>{items}</ul>'

    replacements = {
        '{{PROJECT_NAME}}': project_name,
        '{{ANALYSIS_DATE}}': now,
        '{{TOTAL_FILES}}': stats['total_files'],
        '{{TOTAL_LINES}}': stats['total_lines'],
        '{{TOTAL_BLANK_LINES}}': stats['total_blank_lines'],
        '{{TOTAL_CODE_LINES}}': stats['total_code_lines'],
        '{{TOTAL_COMMENT_LINES}}': stats['total_comment_lines'],
        '{{TOTAL_MIXED_LINES}}': stats['total_mixed_lines'],
        '{{TOTAL_SINGLE_COMMENTS}}': stats['total_single_comments'],
        '{{TOTAL_MULTI_COMMENTS}}': stats['total_multi_comments'],
        '{{TOTAL_CHARACTERS}}': stats['total_characters'],
        '{{TOTAL_DUPLICATE_LINES}}': stats['total_duplicate_lines'],
        '{{DUPLICATE_LINE_RATIO}}': f"{stats['duplicate_line_ratio']}%",
        '{{TOTAL_FUNCTIONS}}': stats['total_functions'],
        '{{TOTAL_CLASSES}}': stats['total_classes'],
        '{{OVERALL_COMMENT_RATIO}}': f"{stats['overall_comment_ratio']}%",
        '{{AVG_COMMENTS_PER_FILE}}': stats['avg_comments_per_file'],
        '{{OVERALL_AVG_LINE_LENGTH}}': stats['overall_avg_line_length'],
        '{{LONGEST_LINE}}': stats['longest_line'],
        '{{SHORTEST_LINE}}': stats['shortest_line'],
        '{{TOTAL_ANALYSIS_TIME}}': f"{stats['total_analysis_time']:.2f}",
        '{{SLOWEST_FILE}}': stats['slowest_file']['path'] if stats['slowest_file'] else 'N/A',
        '{{FASTEST_FILE}}': stats['fastest_file']['path'] if stats['fastest_file'] else 'N/A',
        '{{LANG_ROWS}}': lang_rows,
        '{{LARGEST_FILE_BY_LINES}}': stats['largest_file_by_lines']['path'] if stats['largest_file_by_lines'] else 'N/A',
        '{{SMALLEST_FILE_BY_LINES}}': stats['smallest_file_by_lines']['path'] if stats['smallest_file_by_lines'] else 'N/A',
        '{{LARGEST_FILE_BY_SIZE}}': stats['largest_file_by_size']['path'] if stats['largest_file_by_size'] else 'N/A',
        '{{FILES_OVER_500}}': list_files(stats['files_over_500']),
        '{{EMPTY_FILES}}': list_files(stats['empty_files']),
        '{{FILES_WITHOUT_COMMENTS}}': list_files(stats['files_without_comments']),
        '{{FILES_WITH_MOST_COMMENTS}}': list_files(stats['files_with_most_comments']),
        '{{LINE_LENGTH_BUCKETS}}': buckets_rows
    }
    for key, value in replacements.items():
        template = template.replace(key, str(value))
    output_path.write_text(template, encoding='utf-8')
    logger.info(f"Report generated: {output_path}")


def clean_file(file_path, lang, output_base=None, backup=False):
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
        cleaned = remove_comments_from_text(content, lang)
        if cleaned == content:
            return False
        if output_base:
            rel = file_path.relative_to(
                project_root) if 'project_root' in globals() else file_path.name
            dest = output_base / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(cleaned, encoding='utf-8')
            logger.info(f"Cleaned -> {dest}")
        else:
            if backup:
                shutil.copy2(file_path, file_path.with_suffix(
                    file_path.suffix + '.bak'))
            file_path.write_text(cleaned, encoding='utf-8')
            logger.info(f"Cleaned: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error cleaning {file_path}: {e}")
        return False


def clean_project(project_path, workers, dry_run=False, output_dir=None, backup=False):
    files = collect_files(project_path)
    logger.info(f"Cleaning comments from {len(files)} files")
    if dry_run:
        logger.info("Dry run mode - no changes")
        return
    global project_root
    project_root = project_path
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for f in files:
            lang = get_language(f)
            if lang:
                futures.append(
                    ex.submit(clean_file, f, lang, output_dir, backup))
        for fut in as_completed(futures):
            fut.result()


DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Analysis Report - {{PROJECT_NAME}}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; color: #f59e0b; margin-bottom: 0.5rem; font-size: 2.5rem; }
        .meta { text-align: center; color: #94a3b8; margin-bottom: 2rem; }
        h2 { color: #f59e0b; border-bottom: 2px solid #f59e0b; padding-bottom: 0.5rem; margin: 2rem 0 1rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
        .card { background: #1e293b; border-radius: 0.75rem; padding: 1.5rem; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: transform 0.2s; }
        .card:hover { transform: translateY(-3px); }
        .card .number { font-size: 2rem; font-weight: 700; color: #38bdf8; }
        .card .label { color: #94a3b8; font-size: 0.9rem; margin-top: 0.3rem; }
        table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 0.5rem; overflow: hidden; margin: 1rem 0; }
        th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #0f172a; color: #f59e0b; font-weight: 600; }
        tr:hover { background: #263449; }
        .bar-container { background: #334155; border-radius: 4px; height: 12px; width: 100%; overflow: hidden; }
        .bar { background: linear-gradient(90deg, #38bdf8, #f59e0b); height: 100%; border-radius: 4px; }
        ul { list-style: none; padding-left: 1rem; }
        li { padding: 0.25rem 0; }
        .footer { text-align: center; margin-top: 3rem; color: #64748b; font-size: 0.85rem; }
    </style>
</head>
<body>
<div class="container">
    <h1>📊 {{PROJECT_NAME}}</h1>
    <div class="meta">Generated on {{ANALYSIS_DATE}}</div>

    <h2>Overview</h2>
    <div class="stats-grid">
        <div class="card"><div class="number">{{TOTAL_FILES}}</div><div class="label">Files</div></div>
        <div class="card"><div class="number">{{TOTAL_LINES}}</div><div class="label">Total Lines</div></div>
        <div class="card"><div class="number">{{TOTAL_CODE_LINES}}</div><div class="label">Code Lines</div></div>
        <div class="card"><div class="number">{{TOTAL_COMMENT_LINES}}</div><div class="label">Comment Lines</div></div>
        <div class="card"><div class="number">{{TOTAL_BLANK_LINES}}</div><div class="label">Blank Lines</div></div>
        <div class="card"><div class="number">{{TOTAL_MIXED_LINES}}</div><div class="label">Mixed Lines</div></div>
        <div class="card"><div class="number">{{TOTAL_CHARACTERS}}</div><div class="label">Characters</div></div>
        <div class="card"><div class="number">{{TOTAL_FUNCTIONS}}</div><div class="label">Functions</div></div>
        <div class="card"><div class="number">{{TOTAL_CLASSES}}</div><div class="label">Classes</div></div>
    </div>

    <h2>Language Statistics</h2>
    <table>
        <thead><tr><th>Language</th><th>Files</th><th>Lines</th><th>Code</th><th>Blank</th><th>Comments</th><th>Mixed</th><th>Chars</th><th>% Lines</th><th>Comment Ratio</th><th>Distribution</th></tr></thead>
        <tbody>{{LANG_ROWS}}</tbody>
    </table>

    <h2>Comment Details</h2>
    <div class="stats-grid">
        <div class="card"><div class="number">{{TOTAL_SINGLE_COMMENTS}}</div><div class="label">Single-line</div></div>
        <div class="card"><div class="number">{{TOTAL_MULTI_COMMENTS}}</div><div class="label">Multi-line</div></div>
        <div class="card"><div class="number">{{OVERALL_COMMENT_RATIO}}</div><div class="label">Comment Ratio</div></div>
        <div class="card"><div class="number">{{AVG_COMMENTS_PER_FILE}}</div><div class="label">Avg per File</div></div>
    </div>

    <h2>Line Statistics</h2>
    <div class="stats-grid">
        <div class="card"><div class="number">{{OVERALL_AVG_LINE_LENGTH}}</div><div class="label">Avg Line Length</div></div>
        <div class="card"><div class="number">{{LONGEST_LINE}}</div><div class="label">Longest Line</div></div>
        <div class="card"><div class="number">{{SHORTEST_LINE}}</div><div class="label">Shortest Non-blank</div></div>
        <div class="card"><div class="number">{{DUPLICATE_LINE_RATIO}}</div><div class="label">Duplicate Ratio</div></div>
    </div>
    <table><thead><tr><th>Length Range</th><th>Count</th></tr></thead><tbody>{{LINE_LENGTH_BUCKETS}}</tbody></table>

    <h2>File Highlights</h2>
    <div class="stats-grid">
        <div class="card"><div class="number">{{LARGEST_FILE_BY_LINES}}</div><div class="label">Largest (lines)</div></div>
        <div class="card"><div class="number">{{SMALLEST_FILE_BY_LINES}}</div><div class="label">Smallest (lines)</div></div>
        <div class="card"><div class="number">{{LARGEST_FILE_BY_SIZE}}</div><div class="label">Largest (size)</div></div>
    </div>
    <h3>Files > 500 lines</h3>{{FILES_OVER_500}}
    <h3>Empty Files</h3>{{EMPTY_FILES}}
    <h3>Files Without Comments</h3>{{FILES_WITHOUT_COMMENTS}}
    <h3>Top 10 Most Commented</h3>{{FILES_WITH_MOST_COMMENTS}}

    <h2>Performance</h2>
    <div class="stats-grid">
        <div class="card"><div class="number">{{TOTAL_ANALYSIS_TIME}}s</div><div class="label">Total Time</div></div>
        <div class="card"><div class="number">{{SLOWEST_FILE}}</div><div class="label">Slowest File</div></div>
        <div class="card"><div class="number">{{FASTEST_FILE}}</div><div class="label">Fastest File</div></div>
    </div>
    <div class="footer">Generated by Code Analyzer</div>
</div>
</body>
</html>"""


def run_cli():
    parser = argparse.ArgumentParser(description='Comprehensive Code Analyzer')
    parser.add_argument('path', help='Project directory or file')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of workers')
    parser.add_argument('--remove-comments',
                        action='store_true', help='Remove comments')
    parser.add_argument('--dry-run', action='store_true', help='No changes')
    parser.add_argument(
        '--output-dir', help='Output directory for cleaned files')
    parser.add_argument('--backup', action='store_true',
                        help='Create .bak before modifying')
    parser.add_argument('--output', help='Report file name')
    args = parser.parse_args()

    project_path = Path(args.path).resolve()
    if not project_path.exists():
        logger.error(f"Path does not exist: {project_path}")
        sys.exit(1)

    project_name = project_path.name
    logger.info(f"Starting analysis of: {project_path}")

    files = collect_files(project_path)
    logger.info(f"Found {len(files)} files")
    if not files:
        logger.error("No supported files found")
        sys.exit(1)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(analyze_file, f): f for f in files}
        for fut in as_completed(futures):
            f = futures[fut]
            try:
                res = fut.result()
                if res:
                    results.append(res)
                    logger.info(f"Analyzed: {f}")
            except Exception as e:
                logger.error(f"Failed {f}: {e}")

    if not results:
        logger.error("No valid results")
        sys.exit(1)

    stats = aggregate_stats(results)
    output_name = args.output or f"{project_name}-check.html"
    output_path = Path.cwd() / output_name
    generate_html_report(project_name, stats, output_path)

    if args.remove_comments:
        if args.dry_run:
            logger.info("Dry run - no modifications")
        elif args.output_dir:
            out_dir = Path(args.output_dir).resolve()
            clean_project(project_path, args.workers,
                          dry_run=False, output_dir=out_dir)
        else:
            confirm = input("Remove comments in-place? (y/N): ")
            if confirm.lower() == 'y':
                clean_project(project_path, args.workers, backup=args.backup)
            else:
                logger.info("Cancelled")

    logger.info("Done")
