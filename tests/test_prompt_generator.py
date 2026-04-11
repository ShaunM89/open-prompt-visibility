"""Tests for prompt generation and variation."""

import pytest

from src.prompt_generator import (
    PromptGenerator,
    PromptVariationTracker,
    PromptVariation,
    GeneratedPrompt,
)


@pytest.fixture
def mock_config():
    return {
        "brands": [
            {
                "name": "Nike",
                "keywords": ["Nike", "Swoosh"],
                "domain": "athletic footwear & apparel",
                "subtopics": ["running", "basketball", "sustainability"],
                "competitors": [
                    {"name": "Adidas", "keywords": ["Adidas"]},
                ],
            }
        ],
        "tracking": {},
    }


@pytest.fixture
def generator(mock_config):
    return PromptGenerator(mock_config)


class TestPromptGenerator:
    """Test prompt generation."""

    def test_init_loads_brands(self, generator):
        assert "Nike" in generator.brands

    def test_init_brand_has_keywords(self, generator):
        assert "keywords" in generator.brands["Nike"]

    def test_init_no_llm_adapter_without_config(self, generator):
        assert generator.llm_adapter is None

    def test_synonym_variations(self, generator):
        result = generator._generate_synonym_variations("What are the best running shoes?", 3)
        assert isinstance(result, list)
        assert len(result) <= 3

    def test_synonym_variations_no_match(self, generator):
        result = generator._generate_synonym_variations("quantum physics equations", 3)
        assert result == []

    def test_context_variations(self, generator):
        result = generator._generate_context_variations("What are the best running shoes?", 3)
        assert isinstance(result, list)
        assert len(result) <= 3
        for r in result:
            assert "What are the best running shoes?" in r

    def test_generate_variations_synonym_strategy(self, generator):
        result = generator.generate_variations(
            ["What are the best running shoes?"], num_variations=2, strategy="synonym"
        )
        assert isinstance(result, list)
        for v in result:
            assert isinstance(v, PromptVariation)
            assert v.variation_type == "synonym"

    def test_generate_variations_context_strategy(self, generator):
        result = generator.generate_variations(
            ["What are the best running shoes?"], num_variations=2, strategy="context"
        )
        assert isinstance(result, list)
        for v in result:
            assert isinstance(v, PromptVariation)
            assert v.variation_type == "context"

    def test_generate_domain_prompts_known_brand(self, generator):
        result = generator.generate_domain_prompts("Nike", num_prompts=10)
        assert isinstance(result, list)
        assert len(result) > 0
        for p in result:
            assert isinstance(p, GeneratedPrompt)
            assert p.source_brand == "Nike"
            assert p.generation_method == "template"

    def test_generate_domain_prompts_unknown_brand(self, generator):
        result = generator.generate_domain_prompts("UnknownBrand", num_prompts=10)
        assert result == []

    def test_generate_domain_prompts_specific_categories(self, generator):
        result = generator.generate_domain_prompts("Nike", num_prompts=5, categories=["comparison"])
        assert len(result) > 0
        for p in result:
            assert p.category == "comparison"

    def test_generate_all_prompts_combines_sources(self, generator):
        result = generator.generate_all_prompts(
            manual_prompts=["Test prompt"],
            auto_generated=True,
            variations_enabled=True,
            num_variations=2,
        )
        assert "base" in result
        assert "variations" in result
        assert "auto_generated" in result
        assert "all" in result
        assert "Test prompt" in result["base"]

    def test_generate_all_prompts_no_auto(self, generator):
        result = generator.generate_all_prompts(
            manual_prompts=["Test prompt"],
            auto_generated=False,
            variations_enabled=False,
        )
        assert result["auto_generated"] == []
        assert result["variations"] == []
        assert result["all"] == ["Test prompt"]

    def test_semantic_variations_falls_back_without_llm(self, generator):
        result = generator._generate_semantic_variations("best shoes", 3)
        assert isinstance(result, list)


class TestPromptVariationTracker:
    """Test prompt variation tracking."""

    def test_register_prompt(self):
        tracker = PromptVariationTracker()
        variations = [PromptVariation("base", "var1", "synonym", "rule-based")]
        auto = [GeneratedPrompt("gen1", "comparison", "Nike", "running", "template")]
        count = tracker.register_prompt("base prompt", variations, auto)
        assert count == 2

    def test_is_variation_false_for_base(self):
        tracker = PromptVariationTracker()
        variations = [PromptVariation("base", "var1", "synonym", "rule-based")]
        tracker.register_prompt("base", variations, [])
        assert tracker.is_variation("base") is False

    def test_is_variation_true_for_variant(self):
        tracker = PromptVariationTracker()
        variations = [PromptVariation("base", "var1", "synonym", "rule-based")]
        tracker.register_prompt("base", variations, [])
        assert tracker.is_variation("var1") is True

    def test_is_variation_false_for_unknown(self):
        tracker = PromptVariationTracker()
        assert tracker.is_variation("unknown") is False

    def test_get_base_prompt_for_variant(self):
        tracker = PromptVariationTracker()
        variations = [PromptVariation("base", "var1", "synonym", "rule-based")]
        tracker.register_prompt("base", variations, [])
        assert tracker.get_base_prompt("var1") == "base"

    def test_get_base_prompt_for_base(self):
        tracker = PromptVariationTracker()
        tracker.register_prompt("base", [], [])
        assert tracker.get_base_prompt("base") == "base"

    def test_get_base_prompt_none_for_unknown(self):
        tracker = PromptVariationTracker()
        assert tracker.get_base_prompt("unknown") is None
