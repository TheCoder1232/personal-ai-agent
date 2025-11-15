#!/usr/bin/env python3
"""
Project Analyzer - Generates intelligent refactoring suggestions
Scans Python project and creates detailed reports for AI-assisted fixes
"""

import ast
import os
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Union, Set
from concurrent.futures import ProcessPoolExecutor, as_completed
import toml

# --- Data Classes ---

@dataclass
class FileIssue:
    file: str
    line: int
    issue_type: str
    severity: str  # 'high', 'medium', 'low'
    description: str
    context: str = ""

@dataclass
class AnalyzerConfig:
    exclude_dirs: Set[str] = field(default_factory=lambda: {'.git', '__pycache__', '.pytest_cache', 'venv', '.venv', 'node_modules', 'build', 'dist'})
    file_length_threshold: int = 500
    complexity_threshold_medium: int = 15
    complexity_threshold_high: int = 20
    class_count_threshold: int = 4

# --- AST Visitor for Single-Pass Analysis ---

class FileVisitor(ast.NodeVisitor):
    """
    An AST visitor that collects data for analysis in a single pass.
    """
    def __init__(self, file_path: str, config: AnalyzerConfig):
        self.file_path = file_path
        self.config = config
        self.issues: List[FileIssue] = []
        self.classes: List[ast.ClassDef] = []
        self.functions: List[Union[ast.FunctionDef, ast.AsyncFunctionDef]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append(node)
        self._check_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(node)
        self._check_docstring(node)
        self._check_type_hints(node)
        self._check_complexity(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.functions.append(node)
        self._check_docstring(node)
        self._check_type_hints(node)
        self._check_complexity(node)
        self.generic_visit(node)

    def _check_docstring(self, node: Union[ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef]):
        if node.name.startswith('_'):
            return
        if not ast.get_docstring(node):
            entity_type = "Class" if isinstance(node, ast.ClassDef) else "Function"
            self.issues.append(FileIssue(
                file=self.file_path,
                line=node.lineno,
                issue_type="docstring",
                severity="low",
                description=f"{entity_type} '{node.name}' is missing a docstring",
                context="Public API"
            ))

    def _check_type_hints(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]):
        if node.name.startswith('_') and node.name != '__init__':
            return
        
        missing_hints = []
        if not node.returns and node.name != '__init__':
            missing_hints.append("return type")
        
        for arg in node.args.args:
            if arg.arg not in ('self', 'cls') and not arg.annotation:
                missing_hints.append(f"parameter '{arg.arg}'")
        
        if missing_hints:
            self.issues.append(FileIssue(
                file=self.file_path,
                line=node.lineno,
                issue_type="type_hints",
                severity="low",
                description=f"Function '{node.name}' missing type hints: {', '.join(missing_hints)}",
                context="Public API function"
            ))

    def _check_complexity(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]):
        complexity = self._calculate_complexity(node)
        if complexity > self.config.complexity_threshold_medium:
            severity = "high" if complexity > self.config.complexity_threshold_high else "medium"
            self.issues.append(FileIssue(
                file=self.file_path,
                line=node.lineno,
                issue_type="complexity",
                severity=severity,
                description=f"Function '{node.name}' has complexity {complexity}. Consider refactoring.",
                context=f"Lines {node.lineno}-{getattr(node, 'end_lineno', node.lineno)}"
            ))

    def _calculate_complexity(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.And, ast.Or)):
                complexity += 1
            elif isinstance(child, ast.comprehension): # list/dict/set comprehensions
                complexity += 1
        return complexity

# --- Main Analyzer Class ---

class ProjectAnalyzer:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.issues: List[FileIssue] = []
        self.config = self._load_config()
        # Use a set for faster lookups
        self.stdlib_names = set(sys.stdlib_module_names) if sys.version_info >= (3, 10) else set()

    def _load_config(self) -> AnalyzerConfig:
        """Load config from pyproject.toml or use defaults."""
        pyproject_path = self.project_root / "pyproject.toml"
        config_data = {}
        if pyproject_path.exists():
            try:
                pyproject_data = toml.load(pyproject_path)
                config_data = pyproject_data.get("tool", {}).get("analyzer", {})
            except toml.TomlDecodeError:
                print(f"⚠️  Warning: Could not parse {pyproject_path}. Using default config.")
        
        return AnalyzerConfig(
            exclude_dirs=set(config_data.get("exclude_dirs", AnalyzerConfig().exclude_dirs)),
            file_length_threshold=config_data.get("file_length_threshold", AnalyzerConfig().file_length_threshold),
            complexity_threshold_medium=config_data.get("complexity_threshold_medium", AnalyzerConfig().complexity_threshold_medium),
            complexity_threshold_high=config_data.get("complexity_threshold_high", AnalyzerConfig().complexity_threshold_high),
            class_count_threshold=config_data.get("class_count_threshold", AnalyzerConfig().class_count_threshold),
        )

    def analyze(self):
        """Run all analysis checks in parallel."""
        print(f"🔍 Analyzing project at: {self.project_root}")
        print(f"⚙️  Config: Complexity > {self.config.complexity_threshold_medium} (Medium), > {self.config.complexity_threshold_high} (High). File length > {self.config.file_length_threshold} lines.")
        print("=" * 80)
        
        python_files = self._find_python_files()
        print(f"📁 Found {len(python_files)} Python files to analyze.\n")
        
        all_issues = []
        with ProcessPoolExecutor() as executor:
            future_to_file = {executor.submit(self._analyze_file, file_path, self.config, self.project_root): file_path for file_path in python_files}
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_issues = future.result()
                    if file_issues:
                        all_issues.extend(file_issues)
                except Exception as e:
                    print(f"⚠️  Error analyzing {file_path.relative_to(self.project_root)}: {e}")

        self.issues = sorted(all_issues, key=lambda i: (i.file, i.line))
        self._generate_report()
    
    def _find_python_files(self) -> List[Path]:
        """Find all Python files excluding configured directories."""
        python_files = []
        for path in self.project_root.rglob("*.py"):
            if not any(excluded in path.parts for excluded in self.config.exclude_dirs):
                python_files.append(path)
        return sorted(python_files)
    
    @staticmethod
    def _analyze_file(file_path: Path, config: AnalyzerConfig, project_root: Path) -> List[FileIssue]:
        """Analyze a single Python file and return a list of issues."""
        rel_path_str = str(file_path.relative_to(project_root))
        issues: List[FileIssue] = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.split('\n')
            
            # AST-based analysis
            tree = ast.parse(content)
            visitor = FileVisitor(rel_path_str, config)
            visitor.visit(tree)
            issues.extend(visitor.issues)
            
            # File structure checks (after visiting)
            ProjectAnalyzer._check_file_structure(rel_path_str, visitor.classes, lines, issues, config)
            
            # Text-based analysis
            ProjectAnalyzer._check_comments(rel_path_str, lines, issues)
            ProjectAnalyzer._check_imports(rel_path_str, lines, issues)
            
        except SyntaxError as e:
            issues.append(FileIssue(
                file=rel_path_str,
                line=e.lineno or 0,
                issue_type="syntax_error",
                severity="high",
                description=f"File has a syntax error: {e.msg}"
            ))
        except Exception as e:
            issues.append(FileIssue(file=rel_path_str, line=0, issue_type="analysis_error", severity="high", description=f"Could not analyze file: {e}"))

        return issues

    @staticmethod
    def _check_file_structure(file_path: str, classes: List[ast.ClassDef], lines: List[str], issues: List[FileIssue], config: AnalyzerConfig):
        """Check if file should be split based on content."""
        if len(classes) >= config.class_count_threshold:
            issues.append(FileIssue(
                file=file_path,
                line=1,
                issue_type="file_structure",
                severity="medium",
                description=f"File contains {len(classes)} classes. Consider splitting into separate modules.",
                context=f"Classes: {', '.join([c.name for c in classes[:5]])}"
            ))
        
        if len(lines) > config.file_length_threshold:
            num_functions = 0
            try:
                # A bit expensive, but only for long files.
                tree = ast.parse('\n'.join(lines))
                num_functions = len([n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))])
            except Exception:
                pass # Ignore if parsing fails here
            
            issues.append(FileIssue(
                file=file_path,
                line=1,
                issue_type="file_length",
                severity="low",
                description=f"File is {len(lines)} lines long. Review if it can be logically split.",
                context=f"{len(classes)} classes, {num_functions} functions"
            ))

    @staticmethod
    def _check_comments(file_path: str, lines: List[str], issues: List[FileIssue]):
        """Check for cluttered or commented-out code."""
        comment_block = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                comment_block.append((i, line))
            else:
                if len(comment_block) > 3:
                    ProjectAnalyzer._analyze_comment_block(file_path, comment_block, issues)
                comment_block = []
        if len(comment_block) > 3:
            ProjectAnalyzer._analyze_comment_block(file_path, comment_block, issues)

    @staticmethod
    def _analyze_comment_block(file_path: str, block: List[tuple[int, str]], issues: List[FileIssue]):
        # Check for TODO/FIXME
        todo_lines = [ln for ln, line in block if 'TODO' in line.upper() or 'FIXME' in line.upper()]
        if todo_lines:
            issues.append(FileIssue(
                file=file_path, line=todo_lines[0], issue_type="todo", severity="low",
                description=f"Found {len(todo_lines)} TODO/FIXME comments", context="Technical debt marker"
            ))

        # Check for commented-out code
        code_patterns = ['def ', 'class ', 'import ', 'if ', 'for ', 'while ', '= ']
        code_lines_count = sum(1 for _, line in block if any(p in line for p in code_patterns))
        if code_lines_count / len(block) > 0.5:
            issues.append(FileIssue(
                file=file_path, line=block[0][0], issue_type="commented_code", severity="medium",
                description=f"Found {len(block)} lines of commented-out code. Consider removing if obsolete.",
                context=f"Lines {block[0][0]}-{block[-1][0]}"
            ))

    @staticmethod
    def _check_imports(file_path: str, lines: List[str], issues: List[FileIssue]):
        """Check import organization."""
        import_nodes = [line for line in lines if line.strip().startswith(('import ', 'from '))]
        if not import_nodes:
            return

        # Simple check for now: recommend using a dedicated tool
        issues.append(FileIssue(
            file=file_path,
            line=lines.index(import_nodes[0]) + 1,
            issue_type="import_order",
            severity="low",
            description="Imports may not be organized. Consider using a tool like 'isort' or 'ruff --fix'.",
            context=f"{len(import_nodes)} import statements found."
        ))

    def _generate_report(self):
        """Generate detailed report to console and file."""
        print("\n" + "=" * 80)
        print("📊 ANALYSIS REPORT")
        print("=" * 80 + "\n")
        
        if not self.issues:
            print("✅ No issues found! Project looks good.\n")
            return
        
        by_severity = {'high': [], 'medium': [], 'low': []}
        for issue in self.issues:
            by_severity[issue.severity].append(issue)
        
        print(f"Total Issues: {len(self.issues)}")
        print(f"  🔴 High:   {len(by_severity['high'])}")
        print(f"  🟡 Medium: {len(by_severity['medium'])}")
        print(f"  🔵 Low:    {len(by_severity['low'])}")
        
        for severity in ['high', 'medium', 'low']:
            if issues := by_severity[severity]:
                icon = {'high': '🔴', 'medium': '🟡', 'low': '🔵'}[severity]
                print(f"\n{icon} {severity.upper()} PRIORITY ISSUES ({len(issues)}):")
                print("-" * 40)
                for issue in issues:
                    print(f"\n  - File: {issue.file}:{issue.line}")
                    print(f"    Type: {issue.issue_type}")
                    print(f"    Desc: {issue.description}")
                    if issue.context:
                        print(f"    Ctx:  {issue.context}")
        
        self._save_json_report()
        
        print("\n" + "=" * 80)
        print("💡 Next Steps:")
        print("   1. Review the issues in the report.")
        print("   2. Use an AI assistant to help implement fixes.")
        print("   3. Consider using 'ruff --fix' and 'isort .' to auto-fix formatting issues.")
        print("=" * 80 + "\n")
    
    def _save_json_report(self):
        """Save report as JSON for programmatic access."""
        report_path = self.project_root / "analysis_report.json"
        report_data = {
            "total_issues": len(self.issues),
            "issues": [issue.__dict__ for issue in self.issues]
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, indent=2, fp=f)
            print(f"\n💾 Detailed report saved to: {report_path}")
        except IOError as e:
            print(f"\n⚠️  Could not save JSON report to {report_path}: {e}")


if __name__ == "__main__":
    # Add 'toml' to dependencies if not present
    try:
        import toml
    except ImportError:
        print("Warning: 'toml' library not found. Please run 'pip install toml' for config loading.")

    analyzer = ProjectAnalyzer()
    analyzer.analyze()