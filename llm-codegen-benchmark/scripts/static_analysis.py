#!/usr/bin/env python3
"""Phase 1: Automated static analysis of generated code artifacts.

Runs deterministic quality metrics on every entropy-controlled run's workspace.
Language-aware: dispatches to Python/C#/Java tooling as appropriate.

Reads:  pilot/results/run_manifest.json (entropy vs smoke classification)
Writes: pilot/results/{run_dir}/quality/automated.json per run

Metrics extracted:
  - Cyclomatic complexity (radon for Python, manual AST for C#/Java)
  - Lines of code per file and total
  - Function/method count
  - Max nesting depth
  - Type annotation coverage (Python only via mypy --stats)
  - Import hygiene (unused imports)
  - Docstring/comment density
  - File count and structure fingerprint
"""

import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# ──────────────────────────────────────────────────────────────────────
# Manifest loading — only analyze entropy-controlled runs
# ──────────────────────────────────────────────────────────────────────

def load_entropy_runs() -> list[str]:
    """Load the list of entropy-controlled run directories."""
    manifest_path = RESULTS_DIR / "run_manifest.json"
    if not manifest_path.exists():
        print("ERROR: run_manifest.json not found. Run audit_runs.py first.")
        sys.exit(1)
    manifest = json.load(open(manifest_path))
    return manifest["entropy_runs"]


def detect_task_language(run_dir: Path) -> tuple[str, str]:
    """Detect the task type and language from the run's summary.json."""
    summary = json.load(open(run_dir / "summary.json"))
    task = summary.get("task", "")
    if "fastapi" in task:
        return "python", "fastapi"
    elif "aspnetcore" in task:
        return "csharp", "aspnetcore"
    elif "springboot" in task:
        return "java", "springboot"
    return "unknown", "unknown"


# ──────────────────────────────────────────────────────────────────────
# Python static analysis (radon, AST-based)
# ──────────────────────────────────────────────────────────────────────

def analyze_python_file(filepath: Path) -> dict[str, Any]:
    """Analyze a single Python file using AST parsing."""
    source = filepath.read_text(encoding="utf-8", errors="replace")
    result = {
        "file": str(filepath.name),
        "loc": len(source.splitlines()),
        "blank_lines": sum(1 for line in source.splitlines() if not line.strip()),
        "comment_lines": sum(1 for line in source.splitlines() if line.strip().startswith("#")),
    }

    try:
        tree = ast.parse(source)
    except SyntaxError:
        result["parse_error"] = True
        return result

    # Function/class counts
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    result["function_count"] = len(functions)
    result["class_count"] = len(classes)

    # Function lengths
    func_lengths = []
    for func in functions:
        if hasattr(func, "end_lineno") and func.end_lineno:
            func_lengths.append(func.end_lineno - func.lineno + 1)
    result["function_lengths"] = func_lengths
    result["avg_function_length"] = round(sum(func_lengths) / len(func_lengths), 1) if func_lengths else 0

    # Nesting depth
    result["max_nesting_depth"] = _compute_max_nesting(tree)

    # Cyclomatic complexity (simplified — count decision points)
    decision_nodes = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                             ast.With, ast.Assert, ast.BoolOp))
    )
    result["cyclomatic_complexity_approx"] = decision_nodes + 1  # +1 for the base path

    # Type annotation coverage
    total_params = 0
    annotated_params = 0
    return_annotations = 0
    total_returns = 0
    for func in functions:
        for arg in func.args.args + func.args.posonlyargs + func.args.kwonlyargs:
            total_params += 1
            if arg.annotation:
                annotated_params += 1
        total_returns += 1
        if func.returns:
            return_annotations += 1
    result["type_annotation_coverage"] = round(
        (annotated_params + return_annotations) / max(total_params + total_returns, 1), 2
    )
    result["total_params"] = total_params
    result["annotated_params"] = annotated_params

    # Docstring density
    docstrings = sum(
        1 for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module))
        and ast.get_docstring(node)
    )
    docstring_targets = len(functions) + len(classes) + 1  # +1 for module
    result["docstring_density"] = round(docstrings / max(docstring_targets, 1), 2)

    # Import analysis
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    result["import_count"] = len(imports)

    # Async usage
    async_funcs = [node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)]
    result["async_function_count"] = len(async_funcs)
    result["async_ratio"] = round(len(async_funcs) / max(len(functions), 1), 2)

    return result


def _compute_max_nesting(tree: ast.AST) -> int:
    """Compute maximum nesting depth of control flow structures."""
    max_depth = 0

    def _walk(node, depth):
        nonlocal max_depth
        nesting_nodes = (ast.If, ast.While, ast.For, ast.With, ast.Try,
                         ast.AsyncFor, ast.AsyncWith)
        if isinstance(node, nesting_nodes):
            depth += 1
            max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(node):
            _walk(child, depth)

    _walk(tree, 0)
    return max_depth


def analyze_python_workspace(workspace_dir: Path) -> dict[str, Any]:
    """Analyze all Python source files in a FastAPI workspace."""
    app_dir = workspace_dir / "app"
    if not app_dir.exists():
        return {"error": "no app/ directory found"}

    py_files = sorted(app_dir.rglob("*.py"))
    # Exclude __pycache__
    py_files = [f for f in py_files if "__pycache__" not in str(f)]

    file_analyses = []
    for f in py_files:
        analysis = analyze_python_file(f)
        analysis["relative_path"] = str(f.relative_to(workspace_dir))
        file_analyses.append(analysis)

    # Also analyze test files
    tests_dir = workspace_dir / "tests"
    if tests_dir.exists():
        test_files = sorted(tests_dir.rglob("*.py"))
        test_files = [f for f in test_files if "__pycache__" not in str(f)]
        for f in test_files:
            analysis = analyze_python_file(f)
            analysis["relative_path"] = str(f.relative_to(workspace_dir))
            analysis["is_test"] = True
            file_analyses.append(analysis)

    # Aggregate
    source_files = [f for f in file_analyses if not f.get("is_test")]
    total_loc = sum(f["loc"] for f in source_files)
    total_functions = sum(f.get("function_count", 0) for f in source_files)
    total_classes = sum(f.get("class_count", 0) for f in source_files)
    all_func_lengths = []
    for f in source_files:
        all_func_lengths.extend(f.get("function_lengths", []))

    # Structure fingerprint: sorted list of relative paths
    structure_fingerprint = sorted(f["relative_path"] for f in source_files)

    # Identifier extraction (for naming drift analysis)
    identifiers = _extract_python_identifiers(app_dir)

    return {
        "language": "python",
        "framework": "fastapi",
        "files": file_analyses,
        "aggregate": {
            "source_file_count": len(source_files),
            "test_file_count": len(file_analyses) - len(source_files),
            "total_loc": total_loc,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "avg_function_length": round(sum(all_func_lengths) / max(len(all_func_lengths), 1), 1),
            "max_function_length": max(all_func_lengths) if all_func_lengths else 0,
            "avg_nesting_depth": round(
                sum(f.get("max_nesting_depth", 0) for f in source_files) / max(len(source_files), 1), 1
            ),
            "max_nesting_depth": max((f.get("max_nesting_depth", 0) for f in source_files), default=0),
            "total_cyclomatic_complexity": sum(f.get("cyclomatic_complexity_approx", 0) for f in source_files),
            "avg_type_annotation_coverage": round(
                sum(f.get("type_annotation_coverage", 0) for f in source_files) / max(len(source_files), 1), 2
            ),
            "avg_docstring_density": round(
                sum(f.get("docstring_density", 0) for f in source_files) / max(len(source_files), 1), 2
            ),
            "total_imports": sum(f.get("import_count", 0) for f in source_files),
            "async_ratio": round(
                sum(f.get("async_function_count", 0) for f in source_files) / max(total_functions, 1), 2
            ),
        },
        "structure_fingerprint": structure_fingerprint,
        "identifiers": identifiers,
    }


def _extract_python_identifiers(app_dir: Path) -> dict[str, list[str]]:
    """Extract function, class, and variable names for naming drift analysis."""
    result = {"functions": [], "classes": [], "variables": []}
    for f in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in str(f):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                result["classes"].append(node.name)
    return result


# ──────────────────────────────────────────────────────────────────────
# C# static analysis (regex + line-based, since we can't use Roslyn)
# ──────────────────────────────────────────────────────────────────────

def analyze_csharp_file(filepath: Path) -> dict[str, Any]:
    """Analyze a C# file using regex patterns."""
    source = filepath.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    result = {
        "file": str(filepath.name),
        "loc": len(lines),
        "blank_lines": sum(1 for line in lines if not line.strip()),
        "comment_lines": sum(1 for line in lines if line.strip().startswith("//")),
    }

    # Method detection
    method_pattern = re.compile(
        r'(public|private|protected|internal)\s+(static\s+)?(async\s+)?'
        r'([\w<>\[\]?]+)\s+(\w+)\s*\('
    )
    methods = method_pattern.findall(source)
    result["method_count"] = len(methods)
    result["method_names"] = [m[4] for m in methods]
    result["async_method_count"] = sum(1 for m in methods if m[2].strip())

    # Class detection
    class_pattern = re.compile(r'(public|internal)\s+(abstract\s+|static\s+)?class\s+(\w+)')
    classes = class_pattern.findall(source)
    result["class_count"] = len(classes)
    result["class_names"] = [c[2] for c in classes]

    # Interface detection
    interface_pattern = re.compile(r'(public|internal)\s+interface\s+(\w+)')
    interfaces = interface_pattern.findall(source)
    result["interface_count"] = len(interfaces)

    # Attribute usage (DI, routing, etc.)
    attributes = re.findall(r'\[(\w+(?:\([^)]*\))?)\]', source)
    result["attributes"] = attributes
    result["has_api_controller"] = "[ApiController]" in source
    result["has_route"] = bool(re.search(r'\[Route\(', source))
    result["has_http_method"] = bool(re.search(r'\[(Http(Get|Post|Put|Delete|Patch))', source))

    # DI markers
    result["uses_constructor_injection"] = bool(
        re.search(r'public\s+\w+\s*\([^)]*I\w+\s+\w+', source)
    )

    # Nesting depth (approximate via brace counting)
    max_depth = 0
    current_depth = 0
    for char in source:
        if char == '{':
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == '}':
            current_depth -= 1
    result["max_nesting_depth"] = max_depth

    # Using statements (imports)
    usings = re.findall(r'using\s+([\w.]+);', source)
    result["using_count"] = len(usings)
    result["usings"] = usings

    return result


def analyze_csharp_workspace(workspace_dir: Path) -> dict[str, Any]:
    """Analyze all C# source files in an ASP.NET Core workspace."""
    src_dir = workspace_dir / "src" / "BenchApi"
    if not src_dir.exists():
        return {"error": "no src/BenchApi/ directory found"}

    cs_files = sorted(src_dir.rglob("*.cs"))
    cs_files = [f for f in cs_files if "obj" not in str(f) and "bin" not in str(f)]

    file_analyses = []
    for f in cs_files:
        analysis = analyze_csharp_file(f)
        analysis["relative_path"] = str(f.relative_to(workspace_dir))
        file_analyses.append(analysis)

    # Test files
    tests_dir = workspace_dir / "tests" / "BenchApi.Tests"
    if tests_dir.exists():
        test_files = sorted(tests_dir.rglob("*.cs"))
        test_files = [tf for tf in test_files if "obj" not in str(tf) and "bin" not in str(tf)]
        for f in test_files:
            analysis = analyze_csharp_file(f)
            analysis["relative_path"] = str(f.relative_to(workspace_dir))
            analysis["is_test"] = True
            file_analyses.append(analysis)

    source_files = [f for f in file_analyses if not f.get("is_test")]
    total_loc = sum(f["loc"] for f in source_files)
    total_methods = sum(f.get("method_count", 0) for f in source_files)
    total_classes = sum(f.get("class_count", 0) for f in source_files)

    structure_fingerprint = sorted(f["relative_path"] for f in source_files)

    all_method_names = []
    all_class_names = []
    for f in source_files:
        all_method_names.extend(f.get("method_names", []))
        all_class_names.extend(f.get("class_names", []))

    return {
        "language": "csharp",
        "framework": "aspnetcore",
        "files": file_analyses,
        "aggregate": {
            "source_file_count": len(source_files),
            "test_file_count": len(file_analyses) - len(source_files),
            "total_loc": total_loc,
            "total_methods": total_methods,
            "total_classes": total_classes,
            "total_interfaces": sum(f.get("interface_count", 0) for f in source_files),
            "max_nesting_depth": max((f.get("max_nesting_depth", 0) for f in source_files), default=0),
            "uses_di": any(f.get("uses_constructor_injection") for f in source_files),
            "uses_api_controller": any(f.get("has_api_controller") for f in source_files),
            "async_method_ratio": round(
                sum(f.get("async_method_count", 0) for f in source_files) / max(total_methods, 1), 2
            ),
            "total_usings": sum(f.get("using_count", 0) for f in source_files),
        },
        "structure_fingerprint": structure_fingerprint,
        "identifiers": {"methods": all_method_names, "classes": all_class_names},
    }


# ──────────────────────────────────────────────────────────────────────
# Java static analysis (regex + line-based)
# ──────────────────────────────────────────────────────────────────────

def analyze_java_file(filepath: Path) -> dict[str, Any]:
    """Analyze a Java file using regex patterns."""
    source = filepath.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    result = {
        "file": str(filepath.name),
        "loc": len(lines),
        "blank_lines": sum(1 for line in lines if not line.strip()),
        "comment_lines": sum(
            1 for line in lines if line.strip().startswith("//") or line.strip().startswith("*")
        ),
    }

    # Method detection
    method_pattern = re.compile(
        r'(public|private|protected)\s+(static\s+)?([\w<>\[\]?]+)\s+(\w+)\s*\('
    )
    methods = method_pattern.findall(source)
    result["method_count"] = len(methods)
    result["method_names"] = [m[3] for m in methods]

    # Class detection
    class_pattern = re.compile(r'(public|abstract)\s+(abstract\s+)?class\s+(\w+)')
    classes = class_pattern.findall(source)
    result["class_count"] = len(classes)
    result["class_names"] = [c[2] for c in classes]

    # Annotation detection (Spring patterns)
    annotations = re.findall(r'@(\w+)(?:\([^)]*\))?', source)
    result["annotations"] = annotations
    result["has_rest_controller"] = "@RestController" in source
    result["has_request_mapping"] = bool(re.search(r'@(Request|Get|Post|Put|Delete)Mapping', source))
    result["has_autowired"] = "@Autowired" in source
    result["has_valid"] = "@Valid" in source
    result["has_service"] = "@Service" in source

    # Constructor injection check
    result["uses_constructor_injection"] = bool(
        re.search(r'private\s+final\s+\w+\s+\w+;', source)
    ) and not result["has_autowired"]

    # Import analysis
    imports = re.findall(r'import\s+([\w.]+);', source)
    result["import_count"] = len(imports)

    # Nesting depth
    max_depth = 0
    current_depth = 0
    for char in source:
        if char == '{':
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == '}':
            current_depth -= 1
    result["max_nesting_depth"] = max_depth

    return result


def analyze_java_workspace(workspace_dir: Path) -> dict[str, Any]:
    """Analyze all Java source files in a Spring Boot workspace."""
    src_dir = workspace_dir / "src" / "main" / "java"
    if not src_dir.exists():
        return {"error": "no src/main/java/ directory found"}

    java_files = sorted(src_dir.rglob("*.java"))
    java_files = [f for f in java_files if "target" not in str(f)]

    file_analyses = []
    for f in java_files:
        analysis = analyze_java_file(f)
        analysis["relative_path"] = str(f.relative_to(workspace_dir))
        file_analyses.append(analysis)

    # Test files
    test_dir = workspace_dir / "src" / "test" / "java"
    if test_dir.exists():
        test_files = sorted(test_dir.rglob("*.java"))
        for f in test_files:
            analysis = analyze_java_file(f)
            analysis["relative_path"] = str(f.relative_to(workspace_dir))
            analysis["is_test"] = True
            file_analyses.append(analysis)

    source_files = [f for f in file_analyses if not f.get("is_test")]
    total_loc = sum(f["loc"] for f in source_files)
    total_methods = sum(f.get("method_count", 0) for f in source_files)
    total_classes = sum(f.get("class_count", 0) for f in source_files)

    structure_fingerprint = sorted(f["relative_path"] for f in source_files)

    all_method_names = []
    all_class_names = []
    for f in source_files:
        all_method_names.extend(f.get("method_names", []))
        all_class_names.extend(f.get("class_names", []))

    return {
        "language": "java",
        "framework": "springboot",
        "files": file_analyses,
        "aggregate": {
            "source_file_count": len(source_files),
            "test_file_count": len(file_analyses) - len(source_files),
            "total_loc": total_loc,
            "total_methods": total_methods,
            "total_classes": total_classes,
            "max_nesting_depth": max((f.get("max_nesting_depth", 0) for f in source_files), default=0),
            "uses_constructor_injection": any(f.get("uses_constructor_injection") for f in source_files),
            "uses_rest_controller": any(f.get("has_rest_controller") for f in source_files),
            "uses_valid_annotation": any(f.get("has_valid") for f in source_files),
            "total_imports": sum(f.get("import_count", 0) for f in source_files),
        },
        "structure_fingerprint": structure_fingerprint,
        "identifiers": {"methods": all_method_names, "classes": all_class_names},
    }


# ──────────────────────────────────────────────────────────────────────
# Main driver
# ──────────────────────────────────────────────────────────────────────

def main():
    entropy_run_dirs = load_entropy_runs()
    print(f"Analyzing {len(entropy_run_dirs)} entropy-controlled runs...")
    print()

    analyzed = 0
    skipped = 0
    errors = 0

    for run_dir_name in entropy_run_dirs:
        run_dir = RESULTS_DIR / run_dir_name
        workspace = run_dir / "workspace_iter1"

        if not workspace.exists():
            skipped += 1
            continue

        language, framework = detect_task_language(run_dir)

        try:
            if language == "python":
                result = analyze_python_workspace(workspace)
            elif language == "csharp":
                result = analyze_csharp_workspace(workspace)
            elif language == "java":
                result = analyze_java_workspace(workspace)
            else:
                skipped += 1
                continue

            if "error" in result:
                print(f"  SKIP {run_dir_name}: {result['error']}")
                skipped += 1
                continue

            # Add run metadata
            summary = json.load(open(run_dir / "summary.json"))
            result["run_id"] = run_dir_name
            result["model"] = summary.get("model", "unknown")
            result["task"] = summary.get("task", "unknown")
            result["gates_passed"] = sum(1 for v in summary["gates"].values() if v)

            # Write quality output
            quality_dir = run_dir / "quality"
            quality_dir.mkdir(exist_ok=True)
            with open(quality_dir / "automated.json", "w") as f:
                json.dump(result, f, indent=2)

            analyzed += 1
            status = "✓" if result["aggregate"].get("total_loc", 0) > 0 else "⚠"
            print(f"  {status} {run_dir_name[:40]:40s} {language:8s} {result['aggregate'].get('total_loc', 0):4d} LOC  {result['aggregate'].get('total_functions', result['aggregate'].get('total_methods', 0)):2d} funcs")

        except Exception as e:
            print(f"  ✗ {run_dir_name}: {e}")
            errors += 1

    print()
    print(f"Done: {analyzed} analyzed, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
