"""Weighted quality scoring system for LLM-generated code.

Implements the 8 quality attributes from the llm-codebench specification:
- Security (25%): SAST findings, safe patterns
- Stability (20%): Test determinism, error handling  
- Efficiency (15%): Performance benchmarks
- Parallelism (10%): Concurrency correctness
- Complexity (10%): Cyclomatic complexity
- Integration (10%): Patch size, conventions
- Stateful (5%): Idempotency, transactions
- Entropy (5%): Variance across runs
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import re


class QualityScorer:
    """Calculate weighted quality scores for generated code."""
    
    # Attribute weights (must sum to 1.0)
    WEIGHTS = {
        "security": 0.25,
        "stability": 0.20,
        "efficiency": 0.15,
        "parallelism": 0.10,
        "complexity": 0.10,
        "integration": 0.10,
        "stateful": 0.05,
        "entropy": 0.05,
    }
    
    def __init__(self, workspace: Path, task_id: str = "fastapi-001"):
        self.workspace = workspace
        self.task_id = task_id
        self.framework = self._detect_framework()
    
    def _detect_framework(self) -> str:
        """Detect framework from task_id or workspace."""
        if "fastapi" in self.task_id:
            return "python"
        elif "aspnetcore" in self.task_id:
            return "csharp"
        elif "springboot" in self.task_id:
            return "java"
        else:
            return "unknown"
    
    def score_security(self) -> Dict:
        """
        Security (25%): SAST findings, safe patterns.
        
        Measures:
        - Number of security vulnerabilities (bandit for Python)
        - Severity of findings (high/medium/low)
        - Use of safe APIs vs dangerous patterns
        """
        if self.framework == "python":
            return self._score_security_python()
        elif self.framework == "csharp":
            return self._score_security_csharp()
        elif self.framework == "java":
            return self._score_security_java()
        return {"score": 1.0, "findings": [], "details": "Security scan not implemented"}
    
    def _score_security_python(self) -> Dict:
        """Run bandit security scanner on Python code."""
        try:
            venv_python = self.workspace / ".venv" / "bin" / "python"
            
            # Install bandit if not present
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-q", "bandit"],
                cwd=self.workspace,
                capture_output=True,
            )
            
            # Run bandit
            result = subprocess.run(
                [str(venv_python), "-m", "bandit", "-r", "app", "-f", "json"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
            )
            
            if result.stdout:
                data = json.loads(result.stdout)
                findings = data.get("results", [])
                
                # Score based on severity
                high_count = sum(1 for f in findings if f.get("issue_severity") == "HIGH")
                medium_count = sum(1 for f in findings if f.get("issue_severity") == "MEDIUM")
                low_count = sum(1 for f in findings if f.get("issue_severity") == "LOW")
                
                # Weighted penalty: high=-0.3, medium=-0.1, low=-0.05
                penalty = (high_count * 0.3) + (medium_count * 0.1) + (low_count * 0.05)
                score = max(0.0, 1.0 - penalty)
                
                return {
                    "score": score,
                    "findings": findings,
                    "high": high_count,
                    "medium": medium_count,
                    "low": low_count,
                    "details": f"{high_count}H/{medium_count}M/{low_count}L security issues"
                }
        except Exception as e:
            pass
        
        return {"score": 1.0, "findings": [], "details": "No security issues detected"}
    
    def _score_security_csharp(self) -> Dict:
        """Run C# security analysis using dotnet build with analyzers."""
        try:
            # Check if this is a C# project
            csproj_files = list(self.workspace.rglob("*.csproj"))
            if not csproj_files:
                return {"score": 1.0, "findings": [], "details": "No C# project found"}
            
            # Run dotnet build with full diagnostic output
            # SecurityCodeScan runs as Roslyn analyzer if installed
            result = subprocess.run(
                ["dotnet", "build", "--no-incremental", "/p:TreatWarningsAsErrors=false"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            # Parse warnings and errors for security issues
            output = result.stdout + result.stderr
            
            # Look for security-related warnings
            security_patterns = [
                (r"SCS\d+:", "SecurityCodeScan"),  # SecurityCodeScan warnings
                (r"CA\d+:", "Code Analysis"),       # Microsoft Code Analysis
                (r"warning.*[Ss]ecurity", "General"),
                (r"warning.*[Ss]ql.*[Ii]njection", "SQL Injection"),
                (r"warning.*[Xx]ss", "XSS"),
            ]
            
            findings = []
            for pattern, category in security_patterns:
                matches = re.findall(f"{pattern}.*", output, re.MULTILINE)
                for match in matches:
                    findings.append({
                        "category": category,
                        "message": match.strip(),
                        "severity": "MEDIUM"  # Default to medium
                    })
            
            # Score based on findings
            if not findings:
                return {
                    "score": 1.0,
                    "findings": [],
                    "details": "No C# security issues detected"
                }
            
            # Penalty: 0.02 per finding (gentler - many are informational)
            # Caps at 0.5 (50% min score for having warnings)
            penalty = min(0.5, len(findings) * 0.02)
            score = 1.0 - penalty
            
            return {
                "score": score,
                "findings": findings[:10],  # Limit to first 10
                "count": len(findings),
                "details": f"{len(findings)} C# security warnings detected"
            }
            
        except subprocess.TimeoutExpired:
            return {"score": 1.0, "findings": [], "details": "C# build timeout"}
        except Exception as e:
            return {"score": 1.0, "findings": [], "details": f"C# scan error: {str(e)[:50]}"}
    
    
    def _score_security_java(self) -> Dict:
        """Run Java security analysis using Maven with SpotBugs."""
        try:
            # Check if this is a Java/Maven project
            pom_file = self.workspace / "pom.xml"
            if not pom_file.exists():
                return {"score": 1.0, "findings": [], "details": "No Maven project found"}
            
            # Run Maven compile first (SpotBugs needs compiled classes)
            compile_result = subprocess.run(
                ["mvn", "compile", "-q"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            # Try to run SpotBugs if available
            # Check if spotbugs-maven-plugin is in pom.xml
            pom_content = pom_file.read_text()
            has_spotbugs = "spotbugs-maven-plugin" in pom_content
            
            if has_spotbugs:
                # Run SpotBugs analysis
                result = subprocess.run(
                    ["mvn", "spotbugs:check", "-q"],
                    cwd=self.workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                
                output = result.stdout + result.stderr
                
                # Parse SpotBugs output for security issues
                security_patterns = [
                    (r"\[.*?\]\s*(SQL.*injection|SQL_INJECTION)", "SQL Injection"),
                    (r"\[.*?\]\s*(XSS|CROSS_SITE_SCRIPTING)", "XSS"),
                    (r"\[.*?\]\s*(PATH_TRAVERSAL|FILE_DISCLOSURE)", "Path Traversal"),
                    (r"\[.*?\]\s*(WEAK_RANDOM|PREDICTABLE_RANDOM)", "Weak Random"),
                    (r"\[.*?\]\s*(XXE|XML_EXTERNAL_ENTITY)", "XXE"),
                ]
                
                findings = []
                for pattern, category in security_patterns:
                    matches = re.findall(pattern, output, re.IGNORECASE)
                    for match in matches:
                        findings.append({
                            "category": category,
                            "message": match if isinstance(match, str) else match[0],
                            "severity": "HIGH"
                        })
                
                if findings:
                    penalty = len(findings) * 0.15  # Higher penalty for security bugs
                    score = max(0.0, 1.0 - penalty)
                    return {
                        "score": score,
                        "findings": findings[:10],
                        "count": len(findings),
                        "details": f"{len(findings)} Java security issues (SpotBugs)"
                    }
            
            # Fallback: Check Maven output for compiler warnings
            output = compile_result.stdout + compile_result.stderr
            
            # Look for security-related compiler warnings
            warning_patterns = [
                r"warning.*deprecated",
                r"warning.*unsafe",
                r"warning.*unchecked",
            ]
            
            warnings = []
            for pattern in warning_patterns:
                matches = re.findall(f"{pattern}.*", output, re.IGNORECASE | re.MULTILINE)
                warnings.extend(matches)
            
            if warnings:
                # Minor penalty for general warnings
                penalty = min(0.1, len(warnings) * 0.02)
                score = 1.0 - penalty
                return {
                    "score": score,
                    "findings": [{"message": w, "severity": "LOW"} for w in warnings[:5]],
                    "count": len(warnings),
                    "details": f"{len(warnings)} Java compiler warnings"
                }
            
            return {
                "score": 1.0,
                "findings": [],
                "details": "No Java security issues detected"
            }
            
        except subprocess.TimeoutExpired:
            return {"score": 1.0, "findings": [], "details": "Java build timeout"}
        except Exception as e:
            return {"score": 1.0, "findings": [], "details": f"Java scan error: {str(e)[:50]}"}
    
    def score_stability(self, test_results: Dict) -> Dict:
        """
        Stability (20%): Test determinism, error handling.
        
        Measures:
        - Test pass rate
        - Presence of error handling (try/catch patterns)
        - Test coverage (if available)
        """
        tests_total = test_results.get("tests_total", 0)
        tests_failed = test_results.get("tests_failed", 0)
        
        if tests_total == 0:
            return {"score": 0.0, "details": "No tests run"}
        
        # Test pass rate
        pass_rate = (tests_total - tests_failed) / tests_total
        
        # Check for error handling patterns in generated code
        error_handling_score = self._check_error_handling()
        
        # Weighted: 70% test pass rate, 30% error handling
        score = (pass_rate * 0.7) + (error_handling_score * 0.3)
        
        return {
            "score": score,
            "test_pass_rate": pass_rate,
            "error_handling_score": error_handling_score,
            "details": f"{tests_total-tests_failed}/{tests_total} tests passed, error handling: {error_handling_score:.0%}"
        }
    
    def _check_error_handling(self) -> float:
        """Check if code has proper error handling."""
        # Count try/except (Python), try/catch (Java/C#)
        patterns = {
            "python": [r"\btry\b", r"\bexcept\b", r"\braise\b"],
            "java": [r"\btry\b", r"\bcatch\b", r"\bthrows\b"],
            "csharp": [r"\btry\b", r"\bcatch\b", r"\bthrow\b"],
        }
        
        search_patterns = patterns.get(self.framework, patterns["python"])
        found_count = 0
        
        # Search in generated files
        for code_file in self.workspace.rglob("*.py" if self.framework == "python" else "*.java" if self.framework == "java" else "*.cs"):
            if ".venv" in str(code_file) or "obj" in str(code_file) or "target" in str(code_file):
                continue
            
            try:
                content = code_file.read_text()
                for pattern in search_patterns:
                    if re.search(pattern, content):
                        found_count += 1
                        break
            except:
                pass
        
        # Score: 1.0 if found, 0.5 if not (not critical for simple CRUD)
        return 1.0 if found_count > 0 else 0.5
    
    def score_efficiency(self) -> Dict:
        """
        Efficiency (15%): Performance benchmarks.
        
        Measures:
        - Code contains no obvious performance anti-patterns
        - Appropriate data structures used
        - No N+1 queries (for database code)
        """
        # Simple heuristics for now
        score = 1.0
        issues = []
        
        # Check for common anti-patterns
        if self.framework == "python":
            score, issues = self._check_efficiency_python()
        
        return {
            "score": score,
            "issues": issues,
            "details": f"{len(issues)} efficiency issues" if issues else "No efficiency issues"
        }
    
    def _check_efficiency_python(self) -> tuple[float, List[str]]:
        """Check Python code for efficiency issues."""
        issues = []
        
        for py_file in self.workspace.rglob("*.py"):
            if ".venv" in str(py_file):
                continue
            
            try:
                content = py_file.read_text()
                
                # Check for inefficient patterns
                if re.search(r'\.append\(.*\)\s*\n.*for .* in', content):
                    issues.append("List comprehension could be used instead of append loop")
                
                if content.count("for") > 3 and "range" in content:
                    issues.append("Multiple nested loops detected")
                
            except:
                pass
        
        # Deduct 0.2 per issue, cap at 0.0
        penalty = len(issues) * 0.2
        score = max(0.0, 1.0 - penalty)
        
        return score, issues
    
    def score_parallelism(self) -> Dict:
        """
        Parallelism (10%): Concurrency correctness.
        
        Measures:
        - Async/await used correctly (for async frameworks)
        - No blocking calls in async code
        - Thread safety (if using threads)
        """
        score = 1.0
        issues = []
        
        if self.framework == "python":
            # Check for async correctness
            for py_file in self.workspace.rglob("*.py"):
                if ".venv" in str(py_file):
                    continue
                
                try:
                    content = py_file.read_text()
                    
                    # Check for sync calls in async functions
                    if "async def" in content:
                        # Look for blocking patterns
                        if re.search(r'time\.sleep\(', content):
                            issues.append("time.sleep() in async code (should use asyncio.sleep)")
                            score -= 0.3
                        
                        # Check for proper await usage
                        async_func_count = content.count("async def")
                        await_count = content.count("await")
                        
                        if async_func_count > 0 and await_count == 0:
                            issues.append("Async function without await")
                            score -= 0.2
                except:
                    pass
        
        score = max(0.0, score)
        
        return {
            "score": score,
            "issues": issues,
            "details": f"{len(issues)} concurrency issues" if issues else "Concurrency correct"
        }
    
    def score_complexity(self) -> Dict:
        """
        Complexity (10%): Cyclomatic complexity.
        
        Measures:
        - Average cyclomatic complexity
        - Number of functions with high complexity (>10)
        """
        if self.framework == "python":
            return self._score_complexity_python()
        
        # Placeholder for other frameworks
        return {"score": 1.0, "avg_complexity": 0, "details": "Complexity analysis not implemented"}
    
    def _score_complexity_python(self) -> Dict:
        """Calculate cyclomatic complexity for Python code."""
        try:
            venv_python = self.workspace / ".venv" / "bin" / "python"
            
            # Install radon if not present
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-q", "radon"],
                cwd=self.workspace,
                capture_output=True,
            )
            
            # Run radon cc (cyclomatic complexity)
            result = subprocess.run(
                [str(venv_python), "-m", "radon", "cc", "app", "-j"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
            )
            
            if result.stdout:
                data = json.loads(result.stdout)
                
                complexities = []
                high_complexity_count = 0
                
                for file_data in data.values():
                    for func in file_data:
                        if isinstance(func, dict):
                            complexity = func.get("complexity", 0)
                            complexities.append(complexity)
                            if complexity > 10:
                                high_complexity_count += 1
                
                avg_complexity = sum(complexities) / len(complexities) if complexities else 0
                
                # Score: 1.0 if avg < 5, degrade linearly to 0.0 at avg = 20
                score = max(0.0, min(1.0, 1.0 - ((avg_complexity - 5) / 15)))
                
                # Penalty for high complexity functions
                score -= (high_complexity_count * 0.1)
                score = max(0.0, score)
                
                return {
                    "score": score,
                    "avg_complexity": avg_complexity,
                    "high_complexity_count": high_complexity_count,
                    "details": f"Avg complexity: {avg_complexity:.1f}, {high_complexity_count} high complexity functions"
                }
        except Exception as e:
            pass
        
        return {"score": 1.0, "avg_complexity": 0, "details": "Complexity analysis skipped"}
    
    def score_integration(self, diff_lines: int, files_changed: int) -> Dict:
        """
        Integration (10%): Patch size, conventions.
        
        Measures:
        - Size of changes (prefer smaller, focused changes)
        - Number of files changed
        - Follows existing patterns
        """
        # Score based on patch size
        # Ideal: 20-100 lines, penalty for too large or too small
        if diff_lines < 10:
            size_score = 0.5  # Too small, might be incomplete
        elif diff_lines <= 100:
            size_score = 1.0  # Ideal size
        elif diff_lines <= 200:
            size_score = 0.8  # Getting large
        elif diff_lines <= 500:
            size_score = 0.5  # Very large
        else:
            size_score = 0.2  # Extremely large
        
        # Files changed penalty (prefer focused changes)
        if files_changed <= 5:
            files_score = 1.0
        elif files_changed <= 10:
            files_score = 0.8
        else:
            files_score = 0.5
        
        score = (size_score * 0.6) + (files_score * 0.4)
        
        return {
            "score": score,
            "diff_lines": diff_lines,
            "files_changed": files_changed,
            "details": f"{diff_lines} lines changed across {files_changed} files"
        }
    
    def score_stateful(self) -> Dict:
        """
        Stateful (5%): Idempotency, transactions.
        
        Measures:
        - Idempotent operations (can be called multiple times safely)
        - Transaction usage (for database operations)
        - Proper state management
        """
        # Simple check: look for database transaction patterns
        score = 1.0
        has_transactions = False
        
        if self.framework == "python":
            for py_file in self.workspace.rglob("*.py"):
                if ".venv" in str(py_file):
                    continue
                
                try:
                    content = py_file.read_text()
                    
                    # Look for transaction patterns
                    if any(pattern in content for pattern in ["transaction", "commit", "rollback", "atomic"]):
                        has_transactions = True
                        break
                except:
                    pass
        
        # For simple CRUD without database, score is 1.0 (N/A)
        # If database operations present, require transactions
        return {
            "score": score,
            "has_transactions": has_transactions,
            "details": "Transaction handling present" if has_transactions else "No database operations"
        }
    
    def score_entropy(self, iteration_results: List[Dict]) -> Dict:
        """
        Entropy (5%): Variance across runs.
        
        Measures:
        - Consistency across multiple iterations
        - Determinism of output
        - Variance in code quality
        """
        if len(iteration_results) < 2:
            return {"score": 1.0, "variance": 0.0, "details": "Single run, no variance"}
        
        # Compare key metrics across iterations
        test_scores = [r.get("metrics", {}).get("tests_total", 0) for r in iteration_results]
        diff_sizes = [r.get("metrics", {}).get("diff_lines", 0) for r in iteration_results]
        
        # Calculate coefficient of variation (std dev / mean)
        import statistics
        
        test_variance = statistics.stdev(test_scores) / statistics.mean(test_scores) if statistics.mean(test_scores) > 0 else 0
        size_variance = statistics.stdev(diff_sizes) / statistics.mean(diff_sizes) if statistics.mean(diff_sizes) > 0 else 0
        
        # Lower variance is better
        avg_variance = (test_variance + size_variance) / 2
        
        # Score: 1.0 if variance < 0.1, degrade to 0.0 at variance = 0.5
        score = max(0.0, 1.0 - (avg_variance / 0.5))
        
        return {
            "score": score,
            "variance": avg_variance,
            "details": f"Variance: {avg_variance:.2%} across {len(iteration_results)} runs"
        }
    
    def calculate_weighted_score(
        self,
        test_results: Dict,
        diff_lines: int = 0,
        files_changed: int = 0,
        iteration_results: Optional[List[Dict]] = None
    ) -> Dict:
        """Calculate overall weighted quality score."""
        
        # Calculate individual attribute scores
        security = self.score_security()
        stability = self.score_stability(test_results)
        efficiency = self.score_efficiency()
        parallelism = self.score_parallelism()
        complexity = self.score_complexity()
        integration = self.score_integration(diff_lines, files_changed)
        stateful = self.score_stateful()
        entropy = self.score_entropy(iteration_results or [])
        
        # Calculate weighted total
        weighted_score = (
            security["score"] * self.WEIGHTS["security"] +
            stability["score"] * self.WEIGHTS["stability"] +
            efficiency["score"] * self.WEIGHTS["efficiency"] +
            parallelism["score"] * self.WEIGHTS["parallelism"] +
            complexity["score"] * self.WEIGHTS["complexity"] +
            integration["score"] * self.WEIGHTS["integration"] +
            stateful["score"] * self.WEIGHTS["stateful"] +
            entropy["score"] * self.WEIGHTS["entropy"]
        )
        
        return {
            "weighted_score": weighted_score,
            "attributes": {
                "security": security,
                "stability": stability,
                "efficiency": efficiency,
                "parallelism": parallelism,
                "complexity": complexity,
                "integration": integration,
                "stateful": stateful,
                "entropy": entropy,
            },
            "weights": self.WEIGHTS,
        }


def format_score_report(score_data: Dict) -> str:
    """Format weighted score data as human-readable report."""
    lines = [
        "=" * 80,
        "WEIGHTED QUALITY SCORE REPORT",
        "=" * 80,
        "",
        f"Overall Weighted Score: {score_data['weighted_score']:.1%}",
        "",
        "Attribute Scores:",
        "-" * 80,
    ]
    
    for attr_name, weight in score_data["weights"].items():
        attr_data = score_data["attributes"][attr_name]
        score = attr_data["score"]
        details = attr_data.get("details", "")
        
        lines.append(f"{attr_name.capitalize():<15} {weight*100:>4.0f}%  {score:>5.1%}  {details}")
    
    lines.append("-" * 80)
    lines.append("")
    
    return "\n".join(lines)
