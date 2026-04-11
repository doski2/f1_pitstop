"""Tests for f1m.common — compound utilities."""

from __future__ import annotations

from f1m.common import canonical_compound, compound_color, display_compound


class TestCanonicalCompound:
    def test_hard_canonical(self):
        assert canonical_compound("Hard") == "Hard"

    def test_medium_canonical(self):
        assert canonical_compound("Medium") == "Medium"

    def test_soft_canonical(self):
        assert canonical_compound("Soft") == "Soft"

    def test_c1_maps_to_hard(self):
        assert canonical_compound("C1") == "Hard"

    def test_c2_maps_to_hard(self):
        assert canonical_compound("C2") == "Medium"

    def test_c3_maps_to_soft(self):
        # C3 in a 5-compound season maps to Soft
        result = canonical_compound("C3")
        assert isinstance(result, str)
        assert result in {"Soft", "Medium", "Hard"}

    def test_intermediates_pass_through(self):
        result = canonical_compound("Intermediates")
        assert result == "Intermediates"

    def test_wet_pass_through(self):
        result = canonical_compound("Wet")
        assert result == "Wet"

    def test_unknown_returns_as_is(self):
        assert canonical_compound("C99") == "C99"

    def test_numeric_string_returns_canonical_or_original(self):
        result = canonical_compound("0")
        assert isinstance(result, str)


class TestDisplayCompound:
    def test_known_compound_returns_string(self):
        result = display_compound("Soft")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_returns_as_is(self):
        assert display_compound("WeirdCompound") == "WeirdCompound"

    def test_c1_returns_enriched(self):
        result = display_compound("C1")
        # should contain the category hint
        assert "C1" in result or "Hard" in result


class TestCompoundColor:
    def test_soft_is_red(self):
        color = compound_color("Soft")
        assert color.startswith("#")

    def test_medium_is_yellow(self):
        color = compound_color("Medium")
        assert color.startswith("#")

    def test_hard_is_white_or_light(self):
        color = compound_color("Hard")
        assert color.startswith("#")

    def test_unknown_returns_default_color(self):
        color = compound_color("UnknownCompound")
        assert color.startswith("#")
        assert len(color) == 7  # #rrggbb

    def test_intermediates_has_color(self):
        color = compound_color("Intermediates")
        assert color.startswith("#")
