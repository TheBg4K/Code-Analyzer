# Code Analyzer

I built this because I kept needing to know how much code was in a project and what languages were used, but counting by hand was a pain. This tool does it all in a few seconds and can even remove comments safely if you need a clean version.

## What it does

- Scans a project or a single file and gives you detailed stats
- Counts total lines, code lines, blank lines, comment lines, and mixed lines (code + comment on same line)
- Breaks down languages by percentage, number of files, and lines
- Counts functions and classes (for languages that have them)
- Finds duplicate lines and shows line length distribution
- Can remove comments from files with a dry-run, backup, or output to a separate folder
- Generates a nice HTML report you can open in any browser

## Requirements

- Python 3.7 or newer
- No external libraries needed

## Installation

### Option 1: Install as a package

```bash
git clone https://github.com/yourusername/code-analyzer-pro.git
cd code-analyzer-pro
pip install -e .
```

After that you can run it from anywhere:

```bash
code-analyzer /path/to/project
```

### Option 2: Just use the script

Download `main.py` and `rep_temp.html`, put them in the same folder, then run:

```bash
python main.py /path/to/project
```

## Quick start

```bash
code-analyzer /path/to/your/project
```

This creates a file called `your-project-check.html` in the current directory. Open it with a browser and you'll see the full report.

## Usage

### Basic analysis

```bash
code-analyzer /path/to/project

# Analyze a single file
code-analyzer /path/to/file.py

# Use more workers for big projects
code-analyzer /path/to/project --workers 8

# Save the report with a different name
code-analyzer /path/to/project --output my-report.html
```

I usually use `--workers 8` for anything over a few hundred files. For small projects the default of 4 is fine.

### Removing comments

```bash
# First see what would happen without changing anything
code-analyzer /path/to/project --remove-comments --dry-run

# Remove comments in place (asks for confirmation)
code-analyzer /path/to/project --remove-comments

# Remove comments but keep a .bak backup of each file
code-analyzer /path/to/project --remove-comments --backup

# Write cleaned files to a separate directory instead of touching originals
code-analyzer /path/to/project --remove-comments --output-dir ./clean-version
```

If you want to be safe, always use `--backup` or `--output-dir`. The original files stay untouched when you use `--output-dir`.

### Combined commands

```bash
# Analyze and remove comments with backup
code-analyzer /path/to/project --workers 8 --remove-comments --backup

# Analyze, clean to a separate folder, and save the report
code-analyzer /path/to/project --remove-comments --output-dir ./clean --output report.html

# Fast analysis with 16 workers (only if you have a lot of CPU cores)
code-analyzer /path/to/project --workers 16
```

## What gets analyzed

### Files and lines
- Total number of files
- Total lines (including blank and comment lines)
- Code lines, blank lines, comment lines, mixed lines
- Total characters
- Largest and smallest files by lines and size
- Files with more than 500 lines
- Empty files
- Files without any comments

### Languages
- Percentage of each language
- Number of lines and files per language
- Comment ratio per language
- Total characters per language

### Comments
- Single-line comment count
- Multi-line comment count
- Overall comment-to-code ratio
- Average comments per file
- Top 10 files with the most comments

### Code structure
- Number of functions
- Number of classes
- Duplicate line count and ratio
- Line length distribution (0-20, 21-40, etc.)
- Average line length
- Longest and shortest non-blank line

### Performance
- Total analysis time
- Slowest file to analyze
- Fastest file to analyze

## Supported languages

| Language | Extensions | Comments handled |
|----------|------------|------------------|
| Python | .py | `#`, `""" """`, `''' '''` |
| JavaScript | .js, .mjs, .cjs, .jsx | `//`, `/* */` |
| TypeScript | .ts, .tsx | `//`, `/* */` |
| PHP | .php | `//`, `#`, `/* */` |
| HTML | .html, .htm | `<!-- -->` |
| CSS | .css | `/* */` |
| SCSS / Sass / Less | .scss, .sass, .less | `//`, `/* */` |
| Java | .java | `//`, `/* */` |
| C / C++ | .c, .h, .cpp, .hpp | `//`, `/* */` |
| C# | .cs | `//`, `/* */` |
| Ruby | .rb | `#`, `=begin =end` |
| Go | .go | `//`, `/* */` |
| Rust | .rs | `//`, `/* */` |
| Swift | .swift | `//`, `/* */` |
| Kotlin | .kt, .kts | `//`, `/* */` |
| SQL | .sql | `--`, `/* */` |
| Shell | .sh, .bash, .zsh | `#` |
| PowerShell | .ps1 | `#`, `<# #>` |
| Batch | .bat, .cmd | `REM`, `::` |
| XML | .xml | `<!-- -->` |
| JSON | .json | - |
| YAML | .yaml, .yml | `#` |
| TOML | .toml | `#` |
| INI | .ini | `;`, `#` |
| Markdown | .md | `<!-- -->` |
| LaTeX | .tex | `%` |
| R | .r | `#` |
| Perl | .pl | `#` |
| Lua | .lua | `--`, `--[[ ]]` |

## Things to know

The script automatically skips these folders:

- `node_modules`
- `.git`
- `__pycache__`
- `venv`
- `env`

If you get `No supported files found`, make sure the path is correct and contains files with recognized extensions.

If you get `Permission denied`, try running with `sudo` on Linux or check file permissions.

For large projects, increase `--workers` up to 16. More than that probably won't help and may slow things down.

## Example output

```
Starting analysis of: /home/user/myapp
Found 45 files to analyze.
Analyzed: /home/user/myapp/main.py
Analyzed: /home/user/myapp/utils.py
Analyzed: /home/user/myapp/config.json
...
Analysis completed in 4.32 seconds.
Report generated: myapp-check.html
Done
```

## Using it as a Python module

```python
from code_analyzer.analyzer import analyze_file, collect_files
from pathlib import Path

files = collect_files(Path('/path/to/project'))
for f in files:
    result = analyze_file(f)
    if result:
        print(f"{result['name']}: {result['total_lines']} lines")
```

## Contributing

If you find a bug or have an idea, open an issue or send a pull request. I'm happy to look at improvements.

## License

MIT — do whatever you want with it.
