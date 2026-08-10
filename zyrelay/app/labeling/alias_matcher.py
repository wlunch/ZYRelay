import re

from rapidfuzz.fuzz import ratio

from zyrelay.app.models import DocumentBlock, LabelDefinition, MatchMethod

from .regex_matcher import MatchResult


class AliasMatcher:
    def __init__(self, *, fuzzy_enabled: bool, fuzzy_threshold: float) -> None:
        self.fuzzy_enabled = fuzzy_enabled
        self.fuzzy_threshold = fuzzy_threshold

    def match(self, block: DocumentBlock, label: LabelDefinition) -> list[MatchResult]:
        results = self._exact(block, label)
        if self.fuzzy_enabled:
            results.extend(self._fuzzy(block, label))
        return results

    @staticmethod
    def _exact(block: DocumentBlock, label: LabelDefinition) -> list[MatchResult]:
        results: list[MatchResult] = []
        for alias in sorted(label.aliases, key=len, reverse=True):
            for found in re.finditer(re.escape(alias), block.text, flags=re.IGNORECASE):
                results.append(
                    MatchResult(
                        label_code=label.code,
                        matched_text=found.group(0),
                        normalized_value=found.group(0),
                        start_offset=found.start(),
                        end_offset=found.end(),
                        confidence=0.90,
                        match_method=MatchMethod.ALIAS_EXACT,
                        specificity=len(alias),
                    )
                )
        return results

    def _fuzzy(self, block: DocumentBlock, label: LabelDefinition) -> list[MatchResult]:
        results: list[MatchResult] = []
        tokens = list(re.finditer(r"[\u4e00-\u9fffA-Za-z0-9_-]{2,30}", block.text))
        for token_match in tokens:
            token = token_match.group(0)
            for alias in label.aliases:
                score = ratio(alias.lower(), token.lower())
                if self.fuzzy_threshold <= score < 100:
                    results.append(
                        MatchResult(
                            label_code=label.code,
                            matched_text=token,
                            normalized_value=token,
                            start_offset=token_match.start(),
                            end_offset=token_match.end(),
                            confidence=min(0.85, score / 100),
                            match_method=MatchMethod.ALIAS_FUZZY,
                            specificity=len(alias),
                        )
                    )
        return results
