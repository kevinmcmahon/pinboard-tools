# ABOUTME: Tag similarity detection algorithms
# ABOUTME: Finds similar tags using various string comparison methods

import difflib
import re
from collections import defaultdict


class TagSimilarityDetector:
    """Detect similar tags using various algorithms"""

    def __init__(self, tags: list[str]):
        self.tags = sorted(set(tag.lower() for tag in tags))
        self.tag_set = set(self.tags)

    def find_all_similarities(
        self, threshold: float = 0.8
    ) -> dict[str, list[tuple[str, float, str]]]:
        """Find all types of similarities between tags"""
        similarities: defaultdict[str, list[tuple[str, float, str]]] = defaultdict(list)

        self._find_string_similarities(similarities, threshold)
        self._find_plural_singular_similarities(similarities)
        self._find_abbreviation_similarities(similarities)
        self._find_prefix_suffix_similarities(similarities)

        return dict(similarities)

    def _find_string_similarities(
        self,
        similarities: defaultdict[str, list[tuple[str, float, str]]],
        threshold: float,
    ) -> None:
        """Find string similarity matches"""
        for i, tag1 in enumerate(self.tags):
            for tag2 in self.tags[i + 1 :]:
                ratio = difflib.SequenceMatcher(None, tag1, tag2).ratio()
                if ratio >= threshold and ratio < 1.0:
                    similarities[tag1].append((tag2, ratio, "string_similarity"))

    def _find_plural_singular_similarities(
        self, similarities: defaultdict[str, list[tuple[str, float, str]]]
    ) -> None:
        """Find plural/singular form matches"""
        for tag in self.tags:
            variants = self._get_plural_singular_variants(tag)
            for variant in variants:
                if variant in self.tag_set and variant != tag:
                    similarities[tag].append((variant, 0.9, "plural_singular"))

    def _find_abbreviation_similarities(
        self, similarities: defaultdict[str, list[tuple[str, float, str]]]
    ) -> None:
        """Find abbreviation matches"""
        for tag in self.tags:
            abbreviations = self._get_common_abbreviations(tag)
            for abbr in abbreviations:
                if abbr in self.tag_set:
                    similarities[tag].append((abbr, 0.85, "abbreviation"))

    def _find_prefix_suffix_similarities(
        self, similarities: defaultdict[str, list[tuple[str, float, str]]]
    ) -> None:
        """Find prefix/suffix relationship matches"""
        for i, tag1 in enumerate(self.tags):
            for tag2 in self.tags[i + 1 :]:
                if self._is_prefix_suffix_related(tag1, tag2):
                    similarities[tag1].append((tag2, 0.8, "prefix_suffix"))

    def find_tag_groups(self) -> dict[str, list[str]]:
        """Group tags by common patterns"""
        groups: defaultdict[str, list[str]] = defaultdict(list)

        self._add_prefix_groups(groups)
        self._add_suffix_groups(groups)
        self._add_pattern_groups(groups)

        return dict(groups)

    def _add_prefix_groups(self, groups: defaultdict[str, list[str]]) -> None:
        """Add prefix-based groups to the groups dict"""
        prefix_groups = defaultdict(list)
        for tag in self.tags:
            if len(tag) >= 4:
                prefix = tag[:3]
                prefix_groups[prefix].append(tag)

        for prefix, tags in prefix_groups.items():
            if len(tags) > 1:
                groups[f"prefix_{prefix}"] = tags

    def _add_suffix_groups(self, groups: defaultdict[str, list[str]]) -> None:
        """Add suffix-based groups to the groups dict"""
        suffix_groups = defaultdict(list)
        for tag in self.tags:
            if len(tag) >= 4:
                suffix = tag[-3:]
                suffix_groups[suffix].append(tag)

        for suffix, tags in suffix_groups.items():
            if len(tags) > 1:
                groups[f"suffix_{suffix}"] = tags

    def _add_pattern_groups(self, groups: defaultdict[str, list[str]]) -> None:
        """Add pattern-based groups to the groups dict"""
        pattern_groups: dict[str, list[str]] = {
            "years": [],
            "versions": [],
            "numbered": [],
        }

        for tag in self.tags:
            if re.match(r"^\d{4}$", tag):
                pattern_groups["years"].append(tag)
            elif re.match(r"^v?\d+(\.\d+)*$", tag):
                pattern_groups["versions"].append(tag)
            elif re.search(r"\d+$", tag):
                pattern_groups["numbered"].append(tag)

        for pattern, tags in pattern_groups.items():
            if len(tags) > 1:
                groups[f"pattern_{pattern}"] = tags

    def _get_plural_singular_variants(self, tag: str) -> list[str]:
        """Get possible plural/singular variants of a tag"""
        variants = []

        # Simple pluralization rules
        if tag.endswith("s") and len(tag) > 2:
            variants.append(tag[:-1])  # Remove 's'
            if tag.endswith("ies") and len(tag) > 3:
                variants.append(tag[:-3] + "y")  # flies -> fly
            elif tag.endswith("es") and len(tag) > 2:
                variants.append(tag[:-2])  # boxes -> box
        else:
            variants.append(tag + "s")  # Add 's'
            if tag.endswith("y") and len(tag) > 1:
                variants.append(tag[:-1] + "ies")  # fly -> flies
            elif tag.endswith(("s", "x", "z", "ch", "sh")):
                variants.append(tag + "es")  # box -> boxes

        return [v for v in variants if v != tag]

    def _get_common_abbreviations(self, tag: str) -> list[str]:
        """Get common abbreviations for a tag"""
        abbreviations = []

        # Common abbreviation patterns
        abbr_map = {
            "javascript": ["js"],
            "typescript": ["ts"],
            "python": ["py"],
            "development": ["dev"],
            "production": ["prod"],
            "configuration": ["config"],
            "application": ["app"],
            "database": ["db"],
            "documentation": ["docs", "doc"],
            "repository": ["repo"],
            "environment": ["env"],
            "administrator": ["admin"],
            "management": ["mgmt"],
            "information": ["info"],
        }

        # Check if tag is a known full form
        if tag in abbr_map:
            abbreviations.extend(abbr_map[tag])

        # Check if tag is a known abbreviation
        for full, abbrs in abbr_map.items():
            if tag in abbrs:
                abbreviations.append(full)

        return abbreviations

    def _is_prefix_suffix_related(self, tag1: str, tag2: str) -> bool:
        """Check if two tags are related by prefix/suffix"""
        min_prefix_len = 4
        min_suffix_len = 3

        # Check prefix relationship
        if len(tag1) >= min_prefix_len and len(tag2) >= min_prefix_len:
            if tag1.startswith(tag2) or tag2.startswith(tag1):
                return True

        # Check suffix relationship
        if len(tag1) >= min_suffix_len and len(tag2) >= min_suffix_len:
            if tag1.endswith(tag2) or tag2.endswith(tag1):
                return True

        return False
