"""Structured prompt compilation, classification, and management module."""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from .models import create_adapter

logger = logging.getLogger(__name__)

# --- Constants ---

VALID_INTENTS = ("comparison", "recommendation", "informational", "purchase_intent", "awareness")
VALID_PURCHASE_STAGES = ("awareness", "consideration", "decision", "retention")
VALID_QUERY_TYPES = ("branded", "unbranded")

INTENT_ABBREV = {
    "comparison": "cmp",
    "recommendation": "rec",
    "informational": "inf",
    "purchase_intent": "pur",
    "awareness": "awr",
}

PURCHASE_STAGE_ABBREV = {
    "awareness": "awr",
    "consideration": "con",
    "decision": "dec",
    "retention": "ret",
}


# --- Data Classes ---


@dataclass
class PromptTags:
    """Classification tags for a prompt across 4 dimensions."""

    intent: str = ""
    purchase_stage: str = ""
    topic: str = ""
    query_type: str = ""

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "purchase_stage": self.purchase_stage,
            "topic": self.topic,
            "query_type": self.query_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PromptTags":
        if d is None:
            return cls()
        return cls(
            intent=d.get("intent", ""),
            purchase_stage=d.get("purchase_stage", ""),
            topic=d.get("topic", ""),
            query_type=d.get("query_type", ""),
        )

    def is_complete(self) -> bool:
        return all(
            [
                self.intent in VALID_INTENTS,
                self.purchase_stage in VALID_PURCHASE_STAGES,
                bool(self.topic),
                self.query_type in VALID_QUERY_TYPES,
            ]
        )


@dataclass
class StructuredPrompt:
    """A canonical prompt with its variations and classification tags."""

    canonical_id: str
    prompts: List[str]  # First is canonical, rest are variations
    tags: PromptTags

    def canonical_prompt(self) -> str:
        return self.prompts[0] if self.prompts else ""

    def to_dict(self) -> dict:
        return {
            "canonical_id": self.canonical_id,
            "prompts": self.prompts,
            "tags": self.tags.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StructuredPrompt":
        return cls(
            canonical_id=d.get("canonical_id", ""),
            prompts=d.get("prompts", []),
            tags=PromptTags.from_dict(d.get("tags", {})),
        )


# --- PromptCompiler ---


class PromptCompiler:
    """Generates, classifies, and manages structured prompt test sets."""

    def __init__(self, config: dict):
        """Initialize with project config.

        Uses the analysis LLM adapter from config['analysis'] for generation/classification.
        """
        self.config = config

        # Collect all brand keywords for query_type detection
        self.brand_keywords: List[str] = []
        for brand in config.get("brands", []):
            for kw in brand.get("keywords", []):
                self.brand_keywords.append(kw)
            for comp in brand.get("competitors", []):
                for kw in comp.get("keywords", []):
                    self.brand_keywords.append(kw)

        # Initialize analysis LLM adapter
        analysis_config = config.get("analysis", {})
        adapter_config = {
            "provider": analysis_config.get("provider", "ollama"),
            "model": analysis_config.get("model", "gemma4:e2b"),
            "temperature": analysis_config.get("temperature", 0.3),
        }
        endpoint = analysis_config.get("endpoint")
        if endpoint:
            adapter_config["endpoint"] = endpoint

        try:
            self.llm_adapter = create_adapter(adapter_config)
        except Exception as e:
            logger.warning("Failed to initialize analysis LLM for PromptCompiler: %s", e)
            self.llm_adapter = None

        # Counter for canonical IDs: (intent_abbrev, topic_abbrev) -> count
        self._id_counters: Dict[Tuple[str, str], int] = defaultdict(int)

    # --- ID Generation ---

    def _abbrev_topic(self, topic: str) -> str:
        """Create a short abbreviation for a topic."""
        topic = topic.lower().strip()
        # Common abbreviations
        topic_map = {
            "running": "run",
            "basketball": "bbl",
            "sustainability": "sus",
            "football": "ftb",
            "soccer": "scc",
            "tennis": "tnn",
            "training": "trn",
            "lifestyle": "lfs",
            "performance": "prf",
            "outdoor": "out",
            "fitness": "fit",
            "casual": "csl",
            "general": "gen",
        }
        if topic in topic_map:
            return topic_map[topic]
        # Take first 3 chars
        return re.sub(r"[^a-z]", "", topic)[:3] or "gen"

    def _generate_canonical_id(self, intent: str, topic: str) -> str:
        """Generate a unique canonical ID: {intent_abbrev}_{topic_abbrev}_{seq:03d}"""
        intent_ab = INTENT_ABBREV.get(intent, "unk")
        topic_ab = self._abbrev_topic(topic)
        key = (intent_ab, topic_ab)
        self._id_counters[key] += 1
        return f"{intent_ab}_{topic_ab}_{self._id_counters[key]:03d}"

    def _reset_id_counters(self):
        """Reset ID counters (useful when loading existing prompts)."""
        self._id_counters.clear()

    # --- Query Type Detection ---

    def _detect_query_type(self, prompt: str) -> str:
        """Auto-detect if prompt contains any tracked brand keyword."""
        prompt_upper = prompt.upper()
        for keyword in self.brand_keywords:
            if keyword.upper() in prompt_upper:
                return "branded"
        return "unbranded"

    # --- LLM Calls ---

    def _parse_llm_json(self, raw: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return json.loads(text)

    def _llm_generate_prompts(self, brand: str, keywords: List[str], num: int) -> List[dict]:
        """LLM call to generate structured prompts.

        Returns list of dicts with keys: prompt, intent, purchase_stage, topic, is_branded
        """
        if not self.llm_adapter:
            raise RuntimeError("No analysis LLM available for prompt generation")

        prompt_text = f"""Generate {num} diverse user search queries about {brand} covering topics: {", ".join(keywords)}.

For each query, provide:
1. "prompt" - the user query text (natural, conversational)
2. "intent" - one of: comparison, recommendation, informational, purchase_intent, awareness
3. "purchase_stage" - one of: awareness, consideration, decision, retention
4. "topic" - primary topic from: {", ".join(keywords)}
5. "is_branded" - true if the query mentions "{brand}" or its products explicitly

Distribute queries roughly evenly across all 5 intent types and all 4 purchase stages.
Ensure a good mix of branded and unbranded queries (roughly 40% branded, 60% unbranded).

Return ONLY a JSON array of objects, no other text.
Example:
[
  {{"prompt": "What are the best running shoe brands?", "intent": "comparison", "purchase_stage": "awareness", "topic": "running", "is_branded": false}},
  {{"prompt": "Should I buy Nike Air Max for basketball?", "intent": "purchase_intent", "purchase_stage": "decision", "topic": "basketball", "is_branded": true}}
]"""

        result = self.llm_adapter.query(prompt_text)
        parsed = self._parse_llm_json(result)

        if isinstance(parsed, list):
            return [p for p in parsed if isinstance(p, dict) and "prompt" in p]
        return []

    def _llm_classify(self, prompt: str) -> dict:
        """LLM call to classify a single prompt.

        Returns dict with keys: intent, purchase_stage, topic, query_type
        """
        if not self.llm_adapter:
            raise RuntimeError("No analysis LLM available for classification")

        brand_list = ", ".join(set(self.brand_keywords[:10]))  # Limit to avoid huge prompts

        classify_prompt = f"""Classify this user query for brand visibility tracking:

"{prompt}"

Known brand keywords: {brand_list}

Return ONLY valid JSON (no markdown, no explanation):
{{"intent": "comparison", "purchase_stage": "awareness", "topic": "running", "query_type": "unbranded"}}

Where:
- intent is one of: comparison, recommendation, informational, purchase_intent, awareness
- purchase_stage is one of: awareness, consideration, decision, retention
- topic is a short topic word or phrase
- query_type is "branded" if any brand keyword appears in the query, "unbranded" otherwise"""

        result = self.llm_adapter.query(classify_prompt)
        return self._parse_llm_json(result)

    def _llm_generate_variations(self, canonical: str, num: int = 2) -> List[str]:
        """Generate phrasing variations of a canonical prompt via LLM."""
        if not self.llm_adapter:
            return []

        var_prompt = f"""Generate {num} phrasing variations of this query. Each variation should:
- Preserve the same core intent and topic
- Use different wording, tone, or sentence structure
- Sound like a natural user query

Original: "{canonical}"

Return ONLY a JSON array of strings, no other text.
Example: ["variation 1", "variation 2"]"""

        try:
            result = self.llm_adapter.query(var_prompt)
            parsed = self._parse_llm_json(result)
            if isinstance(parsed, list):
                return [v for v in parsed if isinstance(v, str) and len(v) > 10]
        except Exception as e:
            logger.warning("Variation generation failed: %s", e)
        return []

    # --- Public API ---

    def generate(
        self, brand: str, keywords: List[str], num_prompts: int = 50
    ) -> List[StructuredPrompt]:
        """Generate a full classified prompt set using the analysis LLM.

        Args:
            brand: Brand name to generate prompts for
            keywords: Topic keywords to cover
            num_prompts: Number of canonical prompts to generate

        Returns:
            List of StructuredPrompt objects with tags and variations
        """
        self._reset_id_counters()

        # Generate in batches if needed (LLM may struggle with 100 at once)
        batch_size = 25
        all_generated = []
        remaining = num_prompts

        while remaining > 0:
            batch_num = min(batch_size, remaining)
            try:
                batch = self._llm_generate_prompts(brand, keywords, batch_num)
                all_generated.extend(batch)
            except Exception as e:
                logger.warning("Generation batch failed: %s", e)
                break
            remaining -= batch_num

        # Build StructuredPrompt objects
        structured = []
        for gen in all_generated:
            prompt_text = gen.get("prompt", "")
            if not prompt_text or len(prompt_text) < 10:
                continue

            intent = gen.get("intent", "informational")
            purchase_stage = gen.get("purchase_stage", "awareness")
            topic = gen.get("topic", keywords[0] if keywords else "general")
            is_branded = gen.get("is_branded", False)
            query_type = "branded" if is_branded else "unbranded"

            # Validate values
            if intent not in VALID_INTENTS:
                intent = "informational"
            if purchase_stage not in VALID_PURCHASE_STAGES:
                purchase_stage = "awareness"

            canonical_id = self._generate_canonical_id(intent, topic)

            # Generate variations
            variations = []
            try:
                variations = self._llm_generate_variations(prompt_text, num=2)
            except Exception as e:
                logger.warning("Variation generation failed for '%s...': %s", prompt_text[:30], e)

            all_prompts = [prompt_text] + variations[:2]  # Max 2 variations

            structured.append(
                StructuredPrompt(
                    canonical_id=canonical_id,
                    prompts=all_prompts,
                    tags=PromptTags(
                        intent=intent,
                        purchase_stage=purchase_stage,
                        topic=topic,
                        query_type=query_type,
                    ),
                )
            )

        return structured

    def classify_prompts(
        self, prompts: List[str], brand_keywords: Optional[List[str]] = None
    ) -> List[StructuredPrompt]:
        """Classify existing untagged prompts via LLM.

        Args:
            prompts: List of prompt strings to classify
            brand_keywords: Override brand keywords for query_type detection

        Returns:
            List of StructuredPrompt objects with tags assigned
        """
        self._reset_id_counters()
        keywords = brand_keywords or self.brand_keywords

        structured = []
        for prompt_text in prompts:
            if not prompt_text or not prompt_text.strip():
                continue

            try:
                classification = self._llm_classify(prompt_text)
            except Exception as e:
                logger.warning("Classification failed for '%s...': %s", prompt_text[:30], e)
                classification = {}

            intent = classification.get("intent", "informational")
            purchase_stage = classification.get("purchase_stage", "awareness")
            topic = classification.get("topic", "general")

            # Auto-detect query_type from keywords
            query_type = classification.get("query_type", self._detect_query_type(prompt_text))

            # Validate
            if intent not in VALID_INTENTS:
                intent = "informational"
            if purchase_stage not in VALID_PURCHASE_STAGES:
                purchase_stage = "awareness"

            canonical_id = self._generate_canonical_id(intent, topic)

            structured.append(
                StructuredPrompt(
                    canonical_id=canonical_id,
                    prompts=[prompt_text],
                    tags=PromptTags(
                        intent=intent,
                        purchase_stage=purchase_stage,
                        topic=topic,
                        query_type=query_type,
                    ),
                )
            )

        return structured

    # --- YAML I/O ---

    def load_prompts(self, path: str) -> List[StructuredPrompt]:
        """Load structured prompts from a YAML file.

        Handles both new format (structured entries) and old format (category -> strings).
        """
        file_path = Path(path)
        if not file_path.exists():
            return []

        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return []

        # New format: data has a "prompts" key with a list of structured entries
        if isinstance(data, dict) and "prompts" in data:
            prompts_list = data["prompts"]
            if isinstance(prompts_list, list):
                result = []
                for item in prompts_list:
                    if isinstance(item, dict) and "canonical_id" in item:
                        sp = StructuredPrompt.from_dict(item)
                        result.append(sp)
                    elif isinstance(item, str):
                        # Individual string in new format (treat as untagged)
                        result.append(
                            StructuredPrompt(
                                canonical_id="",
                                prompts=[item],
                                tags=PromptTags(query_type=self._detect_query_type(item)),
                            )
                        )
                return result

        # Old format: dict of category -> list of strings
        # OR: flat dict where values are lists of strings
        if isinstance(data, dict):
            result = []
            for category, prompt_list in data.items():
                if isinstance(prompt_list, list):
                    for p in prompt_list:
                        if isinstance(p, str) and p.strip():
                            result.append(
                                StructuredPrompt(
                                    canonical_id="",
                                    prompts=[p],
                                    tags=PromptTags(query_type=self._detect_query_type(p)),
                                )
                            )
            return result

        return []

    def save_prompts(self, prompts: List[StructuredPrompt], path: str) -> None:
        """Write structured prompts to YAML in new format."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"prompts": [p.to_dict() for p in prompts]}

        with open(file_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def validate_prompts(self, prompts: List[StructuredPrompt]) -> List[str]:
        """Validate all prompts have complete tags and valid canonical IDs.

        Returns list of error messages (empty = all valid).
        """
        errors = []
        seen_ids = set()

        for i, sp in enumerate(prompts):
            idx_label = f"#{i + 1}"
            if sp.canonical_id:
                idx_label = sp.canonical_id

            # Check canonical_id format
            if not sp.canonical_id:
                errors.append(f"{idx_label}: Missing canonical_id")
            elif not re.match(r"^[a-z]{3}_[a-z]{2,4}_\d{3}$", sp.canonical_id):
                errors.append(
                    f"{idx_label}: Invalid canonical_id format '{sp.canonical_id}' (expected: xxx_xxx_NNN)"
                )

            # Check for duplicates
            if sp.canonical_id in seen_ids:
                errors.append(f"{idx_label}: Duplicate canonical_id '{sp.canonical_id}'")
            seen_ids.add(sp.canonical_id)

            # Check prompts list
            if not sp.prompts:
                errors.append(f"{idx_label}: No prompts")
            else:
                for j, p in enumerate(sp.prompts):
                    if not p or not p.strip():
                        errors.append(f"{idx_label}: Empty prompt at position {j + 1}")
                    elif len(p) < 10:
                        errors.append(f"{idx_label}: Suspiciously short prompt: '{p}'")

            # Check tags completeness
            if not sp.tags.intent:
                errors.append(f"{idx_label}: Missing intent tag")
            elif sp.tags.intent not in VALID_INTENTS:
                errors.append(f"{idx_label}: Invalid intent '{sp.tags.intent}'")

            if not sp.tags.purchase_stage:
                errors.append(f"{idx_label}: Missing purchase_stage tag")
            elif sp.tags.purchase_stage not in VALID_PURCHASE_STAGES:
                errors.append(f"{idx_label}: Invalid purchase_stage '{sp.tags.purchase_stage}'")

            if not sp.tags.topic:
                errors.append(f"{idx_label}: Missing topic tag")

            if not sp.tags.query_type:
                errors.append(f"{idx_label}: Missing query_type tag")
            elif sp.tags.query_type not in VALID_QUERY_TYPES:
                errors.append(f"{idx_label}: Invalid query_type '{sp.tags.query_type}'")

        return errors

    def build_prompt_lookup(
        self, structured_prompts: List[StructuredPrompt]
    ) -> Dict[str, Tuple[str, PromptTags]]:
        """Build a lookup mapping every prompt text to (canonical_id, tags).

        Used by the tracker to resolve prompt metadata at query time.
        Both canonical and variation prompts are included.
        """
        lookup = {}
        for sp in structured_prompts:
            for prompt_text in sp.prompts:
                lookup[prompt_text] = (sp.canonical_id, sp.tags)
        return lookup
