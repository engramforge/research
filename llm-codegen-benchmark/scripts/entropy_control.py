#!/usr/bin/env python3
"""
Entropy Control - Automatic variance detection and re-run management

This module measures variance across multiple benchmark runs and determines
when additional runs are needed to achieve statistical confidence.

Usage:
    from entropy_control import EntropyController
    
    controller = EntropyController(min_confidence=0.90, max_runs=5)
    
    results = []
    while controller.should_continue(results):
        result = run_benchmark(...)
        results.append(result)
    
    stats = controller.get_statistics(results)
"""

import statistics
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class EntropyController:
    """
    Manages automatic re-run decisions based on result variance.
    """
    
    def __init__(
        self,
        min_confidence: float = 0.90,
        max_runs: int = 5,
        quality_variance_threshold: float = 0.15,
        gate_variance_threshold: float = 0.3,
    ):
        """
        Initialize entropy controller.
        
        Args:
            min_confidence: Minimum required confidence level (0-1)
            max_runs: Maximum number of runs allowed
            quality_variance_threshold: Max acceptable std dev in quality scores
            gate_variance_threshold: Max acceptable variance in gate pass rates
        """
        self.min_confidence = min_confidence
        self.max_runs = max_runs
        self.quality_variance_threshold = quality_variance_threshold
        self.gate_variance_threshold = gate_variance_threshold
    
    def should_continue(self, results: List[Dict]) -> bool:
        """
        Determine if more runs are needed.
        
        Args:
            results: List of benchmark results
        
        Returns:
            True if more runs needed, False if sufficient
        """
        if not results:
            return True  # Need at least one run
        
        if len(results) < 2:
            return True  # Need at least 2 runs to measure variance
        
        if len(results) >= self.max_runs:
            return False  # Hit max runs limit
        
        # Calculate current statistics
        stats = self.get_statistics(results)
        
        # Check if variance is acceptable
        if stats['quality_std'] > self.quality_variance_threshold:
            return True  # Quality variance too high
        
        if stats['gate_variance'] > self.gate_variance_threshold:
            return True  # Gate variance too high
        
        # Check confidence
        if stats['confidence'] < self.min_confidence:
            return True  # Not confident enough
        
        return False  # All criteria met, no more runs needed
    
    def get_statistics(self, results: List[Dict]) -> Dict:
        """
        Calculate variance and confidence statistics.
        
        Args:
            results: List of benchmark results
        
        Returns:
            Dictionary with statistical measures
        """
        if not results:
            return self._empty_stats()
        
        if len(results) == 1:
            return self._single_run_stats(results[0])
        
        # Extract metrics
        gate_scores = [self._gate_score(r) for r in results]
        
        # Gate statistics
        gate_mean = statistics.mean(gate_scores)
        gate_std = statistics.stdev(gate_scores) if len(gate_scores) > 1 else 0.0
        
        # Quality variance (normalized std dev)
        gate_variance = gate_std / 5.0 if gate_mean > 0 else 0.0  # Normalize by max gates (5)
        
        # Calculate confidence using coefficient of variation
        # Lower CV = higher confidence
        cv = gate_std / gate_mean if gate_mean > 0 else 1.0
        confidence = max(0.0, 1.0 - cv)  # Inverse of CV
        
        # For very low variance, boost confidence
        if gate_std < 0.5 and len(results) >= 3:
            confidence = min(1.0, confidence * 1.2)
        
        # Per-gate variance
        gate_variances = self._calculate_gate_variances(results)
        
        return {
            'runs': len(results),
            'gate_mean': gate_mean,
            'gate_std': gate_std,
            'gate_variance': gate_variance,
            'quality_std': gate_std / 5.0,  # Normalized
            'confidence': confidence,
            'confidence_interval': self._confidence_interval(gate_scores),
            'gate_variances': gate_variances,
            'individual_scores': gate_scores,
        }
    
    def _gate_score(self, result: Dict) -> float:
        """Calculate gate score (0-5) from result."""
        gates = result.get('gates', {})
        return sum(1 for passed in gates.values() if passed)
    
    def _calculate_gate_variances(self, results: List[Dict]) -> Dict:
        """Calculate variance for each individual gate."""
        gate_keys = ['diff_extracted', 'diff_applied', 'tests_passed', 'mypy_passed', 'ruff_passed']
        variances = {}
        
        for gate in gate_keys:
            values = [1 if r.get('gates', {}).get(gate, False) else 0 for r in results]
            if len(values) > 1:
                variances[gate] = {
                    'mean': statistics.mean(values),
                    'std': statistics.stdev(values),
                }
            else:
                variances[gate] = {'mean': values[0] if values else 0, 'std': 0.0}
        
        return variances
    
    def _confidence_interval(self, scores: List[float], confidence_level: float = 0.95) -> Tuple[float, float]:
        """
        Calculate confidence interval for scores.
        
        Uses t-distribution for small samples.
        """
        if len(scores) < 2:
            return (scores[0], scores[0]) if scores else (0, 0)
        
        mean = statistics.mean(scores)
        std = statistics.stdev(scores)
        n = len(scores)
        
        # Simple approximation: mean ± 1.96 * (std / sqrt(n)) for 95% CI
        # For small samples, should use t-distribution, but keeping it simple
        margin = 1.96 * (std / (n ** 0.5))
        
        return (max(0, mean - margin), min(5, mean + margin))
    
    def _empty_stats(self) -> Dict:
        """Return empty statistics."""
        return {
            'runs': 0,
            'gate_mean': 0.0,
            'gate_std': 0.0,
            'gate_variance': 0.0,
            'quality_std': 0.0,
            'confidence': 0.0,
            'confidence_interval': (0, 0),
            'gate_variances': {},
            'individual_scores': [],
        }
    
    def _single_run_stats(self, result: Dict) -> Dict:
        """Return statistics for single run."""
        score = self._gate_score(result)
        return {
            'runs': 1,
            'gate_mean': score,
            'gate_std': 0.0,
            'gate_variance': 0.0,
            'quality_std': 0.0,
            'confidence': 0.0,  # Can't be confident with 1 run
            'confidence_interval': (score, score),
            'gate_variances': {},
            'individual_scores': [score],
        }
    
    def format_statistics(self, stats: Dict) -> str:
        """
        Format statistics for display.
        """
        if stats['runs'] == 0:
            return "No runs completed"
        
        if stats['runs'] == 1:
            return f"Single run: {stats['gate_mean']:.0f}/5 gates passed (confidence: N/A)"
        
        ci_low, ci_high = stats['confidence_interval']
        
        lines = [
            f"Runs: {stats['runs']}",
            f"Gates passed: {stats['gate_mean']:.2f} ± {stats['gate_std']:.2f} / 5",
            f"Variance: {stats['gate_variance']:.3f} (quality std: {stats['quality_std']:.3f})",
            f"Confidence: {stats['confidence']:.1%}",
            f"95% CI: [{ci_low:.2f}, {ci_high:.2f}]",
        ]
        
        # Show per-gate variance if available
        if stats['gate_variances']:
            lines.append("\nPer-gate statistics:")
            for gate, var in stats['gate_variances'].items():
                lines.append(f"  {gate}: {var['mean']:.2f} ± {var['std']:.2f}")
        
        return "\n".join(lines)
    
    def recommend_action(self, stats: Dict) -> str:
        """
        Recommend what to do based on current statistics.
        """
        if stats['runs'] < 2:
            return "Run more iterations to measure variance (need ≥2)"
        
        if stats['runs'] >= self.max_runs:
            if stats['confidence'] < 0.7:
                return f"⚠️  Max runs reached ({self.max_runs}), but confidence is LOW ({stats['confidence']:.1%}). Model may be unreliable for this task."
            return f"Max runs reached ({self.max_runs}), stopping."
        
        if stats['confidence'] >= self.min_confidence and stats['quality_std'] <= self.quality_variance_threshold:
            return f"✅ Confidence sufficient ({stats['confidence']:.1%} ≥ {self.min_confidence:.0%}), variance acceptable ({stats['quality_std']:.3f})"
        
        if stats['quality_std'] > self.quality_variance_threshold:
            return f"🔄 High variance detected ({stats['quality_std']:.3f} > {self.quality_variance_threshold:.3f}), running more iterations..."
        
        if stats['confidence'] < self.min_confidence:
            return f"🔄 Confidence too low ({stats['confidence']:.1%} < {self.min_confidence:.0%}), running more iterations..."
        
        return "Continue running iterations"


def entropy_control_demo():
    """
    Demonstrate entropy controller with simulated results.
    """
    print("="*70)
    print("ENTROPY CONTROL DEMONSTRATION")
    print("="*70)
    
    # Simulate results with varying variance
    
    # Low variance scenario (stable model)
    print("\nScenario 1: Low Variance (Stable Model)")
    print("-" * 70)
    controller = EntropyController(min_confidence=0.90, max_runs=5)
    
    stable_results = [
        {'gates': {'diff_extracted': True, 'diff_applied': True, 'tests_passed': True, 'mypy_passed': True, 'ruff_passed': True}},
        {'gates': {'diff_extracted': True, 'diff_applied': True, 'tests_passed': True, 'mypy_passed': True, 'ruff_passed': True}},
        {'gates': {'diff_extracted': True, 'diff_applied': True, 'tests_passed': True, 'mypy_passed': False, 'ruff_passed': True}},
    ]
    
    stats = controller.get_statistics(stable_results)
    print(controller.format_statistics(stats))
    print(f"\nRecommendation: {controller.recommend_action(stats)}")
    print(f"Should continue? {controller.should_continue(stable_results)}")
    
    # High variance scenario (unstable model)
    print("\n\nScenario 2: High Variance (Unstable Model)")
    print("-" * 70)
    
    unstable_results = [
        {'gates': {'diff_extracted': True, 'diff_applied': True, 'tests_passed': True, 'mypy_passed': True, 'ruff_passed': True}},
        {'gates': {'diff_extracted': True, 'diff_applied': True, 'tests_passed': False, 'mypy_passed': False, 'ruff_passed': False}},
        {'gates': {'diff_extracted': True, 'diff_applied': False, 'tests_passed': False, 'mypy_passed': True, 'ruff_passed': False}},
    ]
    
    stats = controller.get_statistics(unstable_results)
    print(controller.format_statistics(stats))
    print(f"\nRecommendation: {controller.recommend_action(stats)}")
    print(f"Should continue? {controller.should_continue(unstable_results)}")


if __name__ == "__main__":
    entropy_control_demo()
