#!/usr/bin/env python3
"""
Automated Persona Variation Testing

Tests all persona variations by running each through an evaluation pipeline
and comparing scores. Integrates with an external evaluation command
(configurable via --eval-cmd) to run actual assessments.

Usage:
    python test_persona_variations.py --role frontend-developer --questions 5

    # With a custom evaluation command:
    python test_persona_variations.py --role frontend-developer --questions 5 \
        --eval-cmd "python my_evaluator.py"

Part of the Persona Prompt Optimization study:
https://github.com/engramforge/research/tree/main/persona-prompt-optimization
"""

import asyncio
import argparse
import json
import os
import shutil
import subprocess
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from adaptive_persona_optimizer import PersonaVariationGenerator

# Resolve repo root relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
DATA_DIR = REPO_ROOT / "data"


class VariationTester:
    """Tests persona variations and measures their performance."""

    def __init__(self, role_id: str, questions_per_test: int = 3,
                 eval_cmd: str = "python evaluate.py"):
        self.role_id = role_id
        self.questions_per_test = questions_per_test
        self.eval_cmd = eval_cmd
        self.persona_path = PROMPTS_DIR / f"{role_id}.yaml"
        self.backup_path = None
        self.results: List[Dict] = []

    def backup_persona(self):
        """Backup original persona file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.persona_path.with_suffix(f'.yaml.backup_{timestamp}')
        shutil.copy(self.persona_path, self.backup_path)
        print(f"✓ Backed up persona to: {self.backup_path.name}")

    def restore_persona(self):
        """Restore original persona file."""
        if self.backup_path and self.backup_path.exists():
            shutil.copy(self.backup_path, self.persona_path)
            print(f"✓ Restored original persona")

    def apply_variation(self, variation_name: str, variation_prompt: str):
        """Temporarily apply a variation to the persona file."""
        with open(self.persona_path) as f:
            persona = yaml.safe_load(f)

        persona['persona_prompt'] = variation_prompt
        persona['version'] = f"1.0.0-test-{variation_name}"

        with open(self.persona_path, 'w') as f:
            yaml.dump(persona, f, default_flow_style=False, sort_keys=False)

        print(f"✓ Applied variation: {variation_name}")

    async def test_variation(self, variation_name: str, variation_prompt: str) -> Dict:
        """Test a single variation and return results."""
        print(f"\n{'=' * 80}")
        print(f"Testing: {self.role_id} - {variation_name}")
        print(f"{'=' * 80}")
        print(f"Prompt length: {len(variation_prompt)} chars")
        print(f"Word count: {len(variation_prompt.split())}")

        self.apply_variation(variation_name, variation_prompt)

        cmd = self.eval_cmd.split() + [
            '--role', self.role_id,
            '--questions-per-role', str(self.questions_per_test)
        ]

        print(f"\nRunning: {' '.join(cmd)}")
        print(f"Started at: {datetime.now().strftime('%H:%M:%S')}\n")

        start_time = time.time()

        try:
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=0,
                env=env
            )

            if process.stdin:
                process.stdin.write('\n')
                process.stdin.flush()

            output_lines = []
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line.rstrip())
                    output_lines.append(line)

            process.wait(timeout=600)
            elapsed_time = time.time() - start_time

            print(f"\n⏱️  Elapsed time: {elapsed_time:.1f}s ({elapsed_time / 60:.1f} min)")

            if process.returncode != 0:
                print(f"❌ Generation failed with exit code {process.returncode}")
                return {
                    'variation': variation_name,
                    'status': 'failed',
                    'error': f"Exit code {process.returncode}",
                    'elapsed_time': elapsed_time,
                }

            # Find the latest run output directory
            output_dir = DATA_DIR / "runs"
            run_dir_match = None
            run_dirs = sorted(output_dir.glob(f'{self.role_id}_run_*')) if output_dir.exists() else []
            if run_dirs:
                run_dir_match = str(run_dirs[-1])

            if not run_dir_match:
                print(f"❌ Could not find run directory")
                return {
                    'variation': variation_name,
                    'status': 'failed',
                    'error': 'Could not locate output directory',
                    'elapsed_time': elapsed_time,
                }

            print(f"\n📁 Analyzing results from: {run_dir_match}")

            run_dir = Path(run_dir_match)
            scores = []
            costs = []
            models = []
            total_input_tokens = 0
            total_output_tokens = 0
            total_thinking_tokens = 0

            for json_file in run_dir.glob('*.json'):
                if json_file.name in ['progress.json', 'run_summary.json']:
                    continue
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                        if 'score' in data:
                            scores.append(data['score'])
                        if 'cost_usd' in data:
                            costs.append(data['cost_usd'])
                        if 'model' in data:
                            models.append(data['model'])
                        total_input_tokens += data.get('input_tokens', 0)
                        total_output_tokens += data.get('output_tokens', 0)
                        total_thinking_tokens += data.get('thinking_tokens', 0)
                except Exception as e:
                    print(f"⚠️  Could not parse {json_file.name}: {e}")

            if not scores:
                print(f"❌ No scores found in {run_dir}")
                return {
                    'variation': variation_name,
                    'status': 'failed',
                    'error': 'No scores in output',
                    'elapsed_time': elapsed_time,
                }

            avg_score = sum(scores) / len(scores)
            total_cost = sum(costs)
            total_tokens = total_input_tokens + total_output_tokens + total_thinking_tokens
            tokens_per_sec = total_tokens / elapsed_time if elapsed_time > 0 else 0
            model_used = models[0] if models else "unknown"

            result_data = {
                'variation': variation_name,
                'status': 'success',
                'avg_score': avg_score,
                'min_score': min(scores),
                'max_score': max(scores),
                'sample_count': len(scores),
                'total_cost': total_cost,
                'elapsed_time': elapsed_time,
                'model': model_used,
                'tokens': {
                    'input': total_input_tokens,
                    'output': total_output_tokens,
                    'thinking': total_thinking_tokens,
                    'total': total_tokens,
                },
                'tokens_per_sec': {
                    'total': tokens_per_sec,
                    'input': total_input_tokens / elapsed_time if elapsed_time > 0 else 0,
                    'output': total_output_tokens / elapsed_time if elapsed_time > 0 else 0,
                },
                'run_directory': str(run_dir),
            }

            print(f"\n✅ RESULTS:")
            print(f"   Model: {model_used}")
            print(f"   Avg Score: {avg_score:.1f} (range: {min(scores):.1f} – {max(scores):.1f})")
            print(f"   Total Cost: ${total_cost:.4f}")
            print(f"   Elapsed Time: {elapsed_time:.1f}s")
            print(f"   Tokens/sec: {tokens_per_sec:.1f}")

            return result_data

        except subprocess.TimeoutExpired:
            elapsed_time = time.time() - start_time
            print(f"❌ Test timed out after {elapsed_time:.1f}s")
            return {
                'variation': variation_name,
                'status': 'timeout',
                'error': 'Test exceeded 10 minute timeout',
                'elapsed_time': elapsed_time,
            }
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Test failed: {e}")
            return {
                'variation': variation_name,
                'status': 'error',
                'error': str(e),
                'elapsed_time': elapsed_time,
            }

    async def test_all_variations(self) -> List[Dict]:
        """Test all variations and return ranked results."""
        print(f"\n{'=' * 80}")
        print(f"AUTOMATED PERSONA VARIATION TESTING: {self.role_id}")
        print(f"{'=' * 80}\n")

        self.backup_persona()

        with open(self.persona_path) as f:
            base_persona = yaml.safe_load(f)

        generator = PersonaVariationGenerator(base_persona)
        variations = generator.generate_variations()

        print(f"Generated {len(variations)} variations:")
        for name in variations.keys():
            print(f"  - {name}")

        print(f"\nTesting each with {self.questions_per_test} questions...")
        estimated_cost = self.questions_per_test * len(variations) * 0.14
        print(f"Estimated cost: ${estimated_cost:.2f}")
        print(f"Estimated time: ~{len(variations) * 3} minutes\n")

        print("Starting tests in 3 seconds...")
        await asyncio.sleep(3)

        results = []
        try:
            for var_name, var_prompt in variations.items():
                result = await self.test_variation(var_name, var_prompt)
                results.append(result)
                self.results.append(result)
                await asyncio.sleep(2)
        finally:
            self.restore_persona()

        return results

    def print_summary(self):
        """Print ranked summary and save results to JSON."""
        print(f"\n{'=' * 80}")
        print(f"VARIATION TEST RESULTS SUMMARY")
        print(f"{'=' * 80}\n")

        successful = sorted(
            [r for r in self.results if r.get('status') == 'success'],
            key=lambda x: x['avg_score'],
            reverse=True,
        )
        failed = [r for r in self.results if r.get('status') != 'success']

        if successful:
            print("📊 RESULTS (ranked by average score):")
            print("-" * 80)
            print(f"{'Rank':<6} {'Variation':<25} {'Score':<10} {'Tokens/s':<12} {'Time':<10} {'Cost':<10}")
            print("-" * 80)

            for i, result in enumerate(successful, 1):
                rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                tps = result.get('tokens_per_sec', {}).get('total', 0)
                t = result.get('elapsed_time', 0)
                print(f"{rank:<6} {result['variation']:<25} {result['avg_score']:>8.1f}  "
                      f"{tps:>10.1f}  {t:>8.1f}s ${result['total_cost']:.4f}")

            winner = successful[0]
            baseline = next((r for r in successful if r['variation'] == 'baseline'), None)

            print(f"\n{'=' * 80}")
            print(f"🏆 WINNER: {winner['variation']}")
            print(f"{'=' * 80}")
            print(f"Average Score: {winner['avg_score']:.1f}")
            if baseline:
                print(f"Improvement over baseline: {winner['avg_score'] - baseline['avg_score']:+.1f} points")
            print(f"Sample count: {winner['sample_count']}")
            print(f"Total Cost: ${winner['total_cost']:.4f}")

        if failed:
            print(f"\n❌ FAILED TESTS: {len(failed)}")
            for r in failed:
                print(f"   {r['variation']}: {r.get('error', 'Unknown error')}")

        # Save results
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = DATA_DIR / f"variation_test_results_{self.role_id}_{ts}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n💾 Results saved to: {results_file}")
        print(f"\n{'=' * 80}\n")


async def main():
    parser = argparse.ArgumentParser(
        description='Test persona variations automatically'
    )
    parser.add_argument('--role', required=True, help='Role ID to test')
    parser.add_argument('--questions', type=int, default=3,
                        help='Questions per variation test (default: 3)')
    parser.add_argument('--eval-cmd', type=str, default='python evaluate.py',
                        help='Evaluation command to invoke (default: python evaluate.py)')
    args = parser.parse_args()

    tester = VariationTester(args.role, args.questions, args.eval_cmd)
    await tester.test_all_variations()
    tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
