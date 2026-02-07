#!/usr/bin/env python3
"""
Adaptive Persona Optimizer

Generates systematic variations of persona prompts for A/B testing.
Each variation targets a specific content pattern (production scenarios,
quantified metrics, first-person language, conciseness, etc.).

Usage:
    python adaptive_persona_optimizer.py --role frontend-developer

Part of the Persona Prompt Optimization study:
https://github.com/engramforge/research/tree/main/persona-prompt-optimization
"""

import argparse
import yaml
from pathlib import Path
from typing import Dict
import re

# Resolve repo root relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PROMPTS_DIR = REPO_ROOT / "prompts"


class PersonaVariationGenerator:
    """Generates systematic variations of persona prompts."""

    def __init__(self, base_persona: Dict):
        self.base_persona = base_persona
        self.base_prompt = base_persona.get('persona_prompt', '')

    def generate_variations(self) -> Dict[str, str]:
        """Generate systematic variations based on successful patterns."""

        variations = {
            'baseline': self.base_prompt,
        }

        # Based on pattern analysis: successful personas have MORE:
        # - production scenarios (+5.8 correlation)
        # - metrics (+2.0)
        # - first-person language (+1.3)

        variations['more_production'] = self._add_production_scenarios(self.base_prompt)
        variations['more_metrics'] = self._add_metrics(self.base_prompt)
        variations['more_first_person'] = self._enhance_first_person(self.base_prompt)
        variations['concise'] = self._make_concise(self.base_prompt)
        variations['hybrid'] = self._add_metrics(
            self._add_production_scenarios(self.base_prompt)
        )
        variations['claude_xml'] = self._add_claude_xml_structure(self.base_prompt)
        variations['markdown_structure'] = self._add_markdown_structure(self.base_prompt)

        return variations

    def _add_production_scenarios(self, prompt: str) -> str:
        """Add more production/deployment language."""
        if '##' in prompt:
            parts = prompt.split('##', 1)
            injection = """
I've deployed these solutions in production environments and monitored their
performance under real load. Through troubleshooting production incidents, I've
learned to prioritize monitoring and observability. I've maintained systems
handling millions of requests and discovered that proactive monitoring catches
issues before they impact users.

##"""
            return parts[0] + injection + parts[1]
        else:
            return prompt + """

Through production deployments and maintenance, I've learned to balance speed
with reliability. I've troubleshot critical incidents and discovered that
proper logging and monitoring are essential for quick resolution."""

    def _add_metrics(self, prompt: str) -> str:
        """Add more specific metrics and quantified improvements."""
        enhanced = prompt
        metric_count = len(re.findall(r'\d+%|\d+x', enhanced))
        if metric_count < 5:
            paragraphs = enhanced.split('\n\n')
            if len(paragraphs) > 1:
                paragraphs[1] = paragraphs[1].replace(
                    'systems',
                    'systems (achieving 99.9% uptime, handling 100K+ requests/day)'
                ).replace(
                    'improved',
                    'improved by 45%'
                ).replace(
                    'reduced',
                    'reduced by 60%'
                )
                enhanced = '\n\n'.join(paragraphs)
        return enhanced

    def _enhance_first_person(self, prompt: str) -> str:
        """Increase first-person language."""
        enhanced = prompt
        enhanced = enhanced.replace(
            'systems have been',
            "I've built systems that have been"
        )
        enhanced = enhanced.replace(
            'experience shows',
            'I discovered through experience'
        )
        enhanced = enhanced.replace(
            'it is important',
            'I learned that it is important'
        )
        enhanced = enhanced.replace(
            'The best practice',
            'I found the best practice'
        )
        return enhanced

    def _make_concise(self, prompt: str) -> str:
        """Create more concise version by removing filler."""
        concise = prompt
        concise = re.sub(r'\s+that\s+', ' ', concise)
        concise = re.sub(r',\s+which\s+', ', ', concise)

        sentences = concise.split('. ')
        combined = []
        for sent in sentences:
            words = sent.split()
            if len(words) < 8 and combined:
                combined[-1] = combined[-1] + ', ' + sent.lower()
            else:
                combined.append(sent)
        return '. '.join(combined)

    def _add_claude_xml_structure(self, prompt: str) -> str:
        """Add Claude-specific XML tag structure hints."""
        xml_instruction = """
Communication: Structure your responses using XML tags for clarity:

<analysis>
Your understanding of the problem and key considerations
</analysis>

<approach>
Your technical approach and reasoning
</approach>

<implementation>
Specific implementation details, code examples, or solutions
</implementation>

<considerations>
Edge cases, trade-offs, or additional factors to consider
</considerations>

Use these tags to organize your technical responses clearly.

---

"""
        if 'Communication:' in prompt:
            parts = prompt.split('Communication:', 1)
            return parts[0] + xml_instruction + 'Communication:' + parts[1]
        else:
            return prompt + '\n\n' + xml_instruction

    def _add_markdown_structure(self, prompt: str) -> str:
        """Add emphasis on markdown headers and structured sections."""
        markdown_instruction = """
Communication: Always use clear markdown structure:

- Start with ## for main sections (## Problem Analysis, ## Solution, ## Implementation)
- Use ### for subsections
- Use code blocks with language tags: ```python, ```bash, ```yaml
- Use bullet points for lists
- Bold **key concepts** and *italicize* emphasis

Structure every answer with clear hierarchical organization using these markdown elements.

---

"""
        if 'Communication:' in prompt:
            parts = prompt.split('Communication:', 1)
            return parts[0] + markdown_instruction + 'Communication:' + parts[1]
        else:
            return prompt + '\n\n' + markdown_instruction


def main():
    parser = argparse.ArgumentParser(
        description='Generate persona prompt variations for A/B testing'
    )
    parser.add_argument('--role', required=True, help='Role ID to optimize')
    args = parser.parse_args()

    persona_path = PROMPTS_DIR / f"{args.role}.yaml"
    if not persona_path.exists():
        print(f"❌ Persona not found: {persona_path}")
        return

    with open(persona_path) as f:
        base_persona = yaml.safe_load(f)

    generator = PersonaVariationGenerator(base_persona)
    variations = generator.generate_variations()

    print(f"Generated {len(variations)} variations for {args.role}:\n")
    for var_name, var_prompt in variations.items():
        first_person = len(re.findall(r"I've|I \w+ed|In my experience", var_prompt))
        production = len(re.findall(r'production|deployment|troubleshooting', var_prompt, re.I))
        print(f"  {var_name}:")
        print(f"    Length: {len(var_prompt)} chars, {len(var_prompt.split())} words")
        print(f"    First-person: {first_person}, Production terms: {production}")


if __name__ == "__main__":
    main()
