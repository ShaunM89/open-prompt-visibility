"""Prompt generation and variation module for query fan-out."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .models import OllamaAdapter


@dataclass
class PromptVariation:
    """Represents a prompt variation."""

    original_prompt: str
    variation: str
    variation_type: str
    source: str  # 'semantic', 'synonym', 'context', etc.


@dataclass
class GeneratedPrompt:
    """Represents an auto-generated prompt with metadata."""

    prompt: str
    category: str
    source_brand: str
    subtopic: str
    generation_method: str  # 'template', 'llm', 'hybrid'


class PromptGenerator:
    """Generates prompt variations and auto-generates prompts from brand domains."""

    # Template patterns for generating prompts from brand domain
    PROMPT_TEMPLATES = {
        "comparison": [
            "Compare {brand} vs competitors for {use_case}",
            "Which is better for {use_case}: {brand} or other brands?",
            "{brand} vs competitors: which excels in {use_case}?",
            "How does {brand} compare to other {category} brands?",
        ],
        "recommendation": [
            "I'm looking for {use_case}, which {brand} should I choose?",
            "What's the best {brand} for {use_case}?",
            "Recommend a {brand} product for {use_case}",
            "For {use_case}, which {brand} would you recommend?",
        ],
        "trends": [
            "What are the leading {brand} products in {year}?",
            "What's trending in {brand} for {use_case}?",
            "Which {brand} innovations are gaining popularity in {use_case}?",
            "What's new from {brand} in the {use_case} space?",
        ],
        "expertise": [
            "Which {brand} is most associated with {attribute}?",
            "{brand} is known for {attribute}, true or false?",
            "What makes {brand} unique in terms of {attribute}?",
            "How does {brand} demonstrate expertise in {attribute}?",
        ],
        "purchase_intent": [
            "I need {criteria}, should I go with {brand}?",
            "Is {brand} a good choice for {criteria}?",
            "Considering {criteria}, is {brand} worth it?",
            "For {criteria}, would {brand} be a wise purchase?",
        ],
        "awareness": [
            "Name the top {count} {category} brands including {brand}",
            "List popular {category} brands, is {brand} among them?",
            "Which {brand} is most recognized in {category}?",
            "Where does {brand} rank among {category} brands?",
        ],
    }

    # Synonym replacements for creating variations
    SYNONYM_MAP = {
        "best": ["top", "finest", "outstanding", "superior", "leading"],
        "compare": ["evaluate", "assess", "contrast", "weigh"],
        "recommend": ["suggest", "advise", "endorse", "propose"],
        "better": ["superior", "preferred", "improved", "enhanced"],
        "top": ["premier", "leading", "foremost", "principal"],
        "popular": ["well-known", "renowned", "favored", "celebrated"],
        "excellent": ["outstanding", "exceptional", "superb", "magnificent"],
        "great": ["wonderful", "fantastic", "remarkable", "impressive"],
        "which": ["what", "what are the", "can you tell me the"],
        "what": ["which", "can you tell me", "I wonder what"],
    }

    def __init__(self, config: dict):
        """Initialize prompt generator with configuration."""
        self.config = config
        self.brands = self._load_brands(config.get("brands", []))

        # Initialize LLM adapter for semantic variations
        llm_config = config.get("tracking", {}).get("llm_detection", {})
        if llm_config and llm_config.get("model") == "ollama":
            self.llm_adapter = OllamaAdapter(
                model=llm_config.get("model", "qwen2.5:7b"), temperature=0.7
            )
        else:
            self.llm_adapter = None

    def _load_brands(self, brands_config: List[dict]) -> Dict[str, dict]:
        """Load brands configuration."""
        brands = {}
        for brand in brands_config:
            brands[brand["name"]] = {
                "keywords": brand.get("keywords", []),
                "competitors": brand.get("competitors", []),
                "domain": brand.get("domain", ""),
                "subtopics": brand.get("subtopics", []),
                "target_audience": brand.get("target_audience", []),
            }
        return brands

    def generate_variations(
        self, base_prompts: List[str], num_variations: int = 3, strategy: str = "semantic"
    ) -> List[PromptVariation]:
        """Generate variations of base prompts.

        Args:
            base_prompts: List of original prompts
            num_variations: Number of variations per prompt
            strategy: One of 'semantic', 'synonym', 'context', 'full'

        Returns:
            List of PromptVariation objects
        """
        variations = []

        for prompt in base_prompts:
            if strategy == "semantic" or strategy == "full":
                var_type = "semantic"
                generated = self._generate_semantic_variations(prompt, num_variations)
                variations.extend(
                    [PromptVariation(prompt, var, var_type, "llm") for var in generated]
                )

            if strategy == "synonym" or strategy == "full":
                var_type = "synonym"
                generated = self._generate_synonym_variations(prompt, num_variations)
                variations.extend(
                    [PromptVariation(prompt, var, var_type, "rule-based") for var in generated]
                )

            if strategy == "context" or strategy == "full":
                var_type = "context"
                generated = self._generate_context_variations(prompt, num_variations)
                variations.extend(
                    [PromptVariation(prompt, var, var_type, "rule-based") for var in generated]
                )

            # Limit total variations per prompt
            total_per_prompt = len([v for v in variations if v.original_prompt == prompt])
            if total_per_prompt > num_variations * 2:
                variations = [v for v in variations if v.original_prompt != prompt]

        return variations

    def _generate_semantic_variations(self, prompt: str, num_variations: int) -> List[str]:
        """Use LLM to generate semantically similar variations."""
        if not self.llm_adapter:
            return []

        try:
            gen_prompt = f"""Generate {num_variations} semantically similar but linguistically diverse 
variations of this query. Focus on capturing the same intent/topic with different 
wording, tone, and structure. Keep the core meaning intact.

Original query: "{prompt}"

Return ONLY as a JSON array of strings, no other text.
Example format: ["variation 1", "variation 2", "variation 3"]
"""
            result = self.llm_adapter.query(gen_prompt)

            # Clean and parse
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            variations = json.loads(result)

            # Validate
            if isinstance(variations, list):
                return [v for v in variations if isinstance(v, str) and len(v) > 10]
            return []

        except Exception:
            # Fall back to synonym variations
            return self._generate_synonym_variations(prompt, num_variations)

    def _generate_synonym_variations(self, prompt: str, max_variations: int) -> List[str]:
        """Generate variations by replacing words with synonyms."""
        variations = []

        for word, synonym_list in self.SYNONYM_MAP.items():
            # Case-insensitive replacement
            pattern = r"\b" + word + r"\b"
            if re.search(pattern, prompt, re.IGNORECASE):
                for synonym in synonym_list[:2]:  # Use first 2 synonyms
                    variation = re.sub(pattern, synonym, prompt, count=1, flags=re.IGNORECASE)
                    if variation != prompt:
                        variations.append(variation)

            if len(variations) >= max_variations * 2:
                break

        # Ensure we don't exceed max_variations
        return variations[:max_variations] if variations else []

    def _generate_context_variations(self, prompt: str, max_variations: int) -> List[str]:
        """Generate variations by adding user context/scenario."""
        variations = []

        contexts = [
            "As a consumer, would you say: {prompt}",
            "From a user perspective: {prompt}",
            "I'm trying to decide. {prompt}",
            "What's your take? {prompt}",
            "In my experience, {prompt} is often debated. What do you think?",
        ]

        for context in contexts[:max_variations]:
            variations.append(context.format(prompt=prompt))

        return variations[:max_variations]

    def generate_domain_prompts(
        self, brand_name: str, num_prompts: int = 15, categories: Optional[List[str]] = None
    ) -> List[GeneratedPrompt]:
        """Generate prompts based on brand domain and subtopics.

        Args:
            brand_name: The brand to generate prompts for
            num_prompts: Total number of prompts to generate
            categories: Specific categories to use, or all if None

        Returns:
            List of GeneratedPrompt objects
        """
        if brand_name not in self.brands:
            return []

        brand = self.brands[brand_name]
        domain = brand.get("domain", brand_name)
        subtopics = brand.get("subtopics", ["general"])

        if categories is None:
            categories = list(self.PROMPT_TEMPLATES.keys())

        # Calculate prompts per category
        per_category = max(1, num_prompts // len(categories))
        generated_prompts = []

        for category in categories[:]:
            if category not in self.PROMPT_TEMPLATES:
                continue

            templates = self.PROMPT_TEMPLATES[category]
            num_templates = min(len(templates), per_category)

            for i, template in enumerate(templates[:num_templates]):
                # Fill in template variables
                use_case = subtopics[i % len(subtopics)] if subtopics else "general"
                category_word = (
                    brand.get("domain", "").split()[0] if brand.get("domain") else "products"
                )

                try:
                    prompt = template.format(
                        brand=brand_name,
                        use_case=use_case,
                        category=category_word,
                        year="2026",
                        attribute=subtopics[0] if subtopics else "quality",
                        criteria=use_case,
                        count=5,
                    )

                    generated_prompts.append(
                        GeneratedPrompt(
                            prompt=prompt,
                            category=category,
                            source_brand=brand_name,
                            subtopic=use_case,
                            generation_method="template",
                        )
                    )
                except KeyError:
                    # Skip if template has unknown variable
                    continue

        # Generate remaining with LLM if still need more
        remaining = num_prompts - len(generated_prompts)
        if remaining > 0 and self.llm_adapter:
            try:
                llm_prompt = f"""Generate {remaining} natural user queries about {brand_name} 
in the context of {domain}. Use diverse phrasings and cover different aspects 
like {", ".join(subtopics[:3])}.

Return ONLY as a JSON array of strings, no other text.
"""
                result = self.llm_adapter.query(llm_prompt)
                result = result.strip()
                if result.startswith("```json"):
                    result = result[7:]
                if result.endswith("```"):
                    result = result[:-3]

                llm_prompts = json.loads(result)

                if isinstance(llm_prompts, list):
                    for prompt in llm_prompts[:remaining]:
                        if isinstance(prompt, str) and len(prompt) > 10:
                            generated_prompts.append(
                                GeneratedPrompt(
                                    prompt=prompt,
                                    category="llm_generated",
                                    source_brand=brand_name,
                                    subtopic="general",
                                    generation_method="llm",
                                )
                            )
            except Exception:
                pass

        return generated_prompts[:num_prompts]

    def generate_all_prompts(
        self,
        manual_prompts: List[str],
        auto_generated: bool = True,
        variations_enabled: bool = True,
        num_variations: int = 3,
    ) -> Dict[str, List[str]]:
        """Combine manual prompts with auto-generated and variations.

        Args:
            manual_prompts: User-provided base prompts
            auto_generated: Whether to generate domain-based prompts
            variations_enabled: Whether to add variations
            num_variations: Number of variations per prompt

        Returns:
            Dictionary with 'base', 'variations', 'auto_generated', and 'all' keys
        """
        result = {
            "base": manual_prompts.copy(),
            "variations": [],
            "auto_generated": [],
            "all": manual_prompts.copy(),
        }

        # Generate variations
        if variations_enabled and manual_prompts:
            vars = self.generate_variations(manual_prompts, num_variations, strategy="full")
            result["variations"] = [v.variation for v in vars]
            result["all"].extend(result["variations"])

        # Generate auto-prompts
        if auto_generated:
            for brand_name in self.brands.keys():
                gen_prompts = self.generate_domain_prompts(brand_name, num_prompts=5)
                result["auto_generated"].extend([gp.prompt for gp in gen_prompts])
                result["all"].extend([gp.prompt for gp in gen_prompts])

        return result


class PromptVariationTracker:
    """Track which variants were used in actual queries."""

    def __init__(self):
        self.prunes = {}

    def register_prompt(
        self,
        base_prompt: str,
        variations: List[PromptVariation],
        auto_generated: List[GeneratedPrompt],
    ) -> int:
        """Register a batch of prompts with their metadata."""
        import uuid

        batch_id = str(uuid.uuid4())[:8]
        self.prunes[batch_id] = {
            "base_prompt": base_prompt,
            "variations": [v.__dict__ for v in variations],
            "auto_generated": [vg.__dict__ for vg in auto_generated],
        }
        return len(self.prunes[batch_id]["variations"]) + len(
            self.prunes[batch_id]["auto_generated"]
        )

    def is_variation(self, prompt: str) -> bool:
        """Check if a prompt is a variation of a base prompt."""
        for batch in self.prunes.values():
            if prompt == batch["base_prompt"]:
                return False
            for var in batch["variations"]:
                if var["variation"] == prompt:
                    return True
        return False

    def get_base_prompt(self, prompt: str) -> Optional[str]:
        """Get the base prompt for a given prompt if it exists."""
        for batch in self.prunes.values():
            if prompt == batch["base_prompt"]:
                return prompt
            for var in batch["variations"]:
                if var["variation"] == prompt:
                    return batch["base_prompt"]
        return None
