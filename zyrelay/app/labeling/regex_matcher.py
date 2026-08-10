import re
from dataclasses import dataclass

from zyrelay.app.models import DocumentBlock, LabelDefinition, MatchMethod


@dataclass(frozen=True)
class MatchResult:
    label_code: str
    matched_text: str
    normalized_value: str
    start_offset: int
    end_offset: int
    confidence: float
    match_method: MatchMethod
    specificity: int


class RegexMatcher:
    def match(self, block: DocumentBlock, label: LabelDefinition) -> list[MatchResult]:
        results: list[MatchResult] = []
        for pattern_text in label.patterns:
            pattern = re.compile(pattern_text)
            for match in pattern.finditer(block.text):
                captured = [
                    group
                    for group in match.groups()
                    if group is not None and group != ""
                ]
                value = captured[-1] if captured else match.group(0)
                results.append(
                    MatchResult(
                        label_code=label.code,
                        matched_text=match.group(0),
                        normalized_value=value.strip(),
                        start_offset=match.start(),
                        end_offset=match.end(),
                        confidence=0.95,
                        match_method=MatchMethod.REGEX,
                        specificity=len(pattern_text),
                    )
                )
        return results
