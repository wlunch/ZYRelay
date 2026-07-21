from collections import Counter

from zyrelay.app.models import LabelMention

from .config_repository import CodeRulePatternConfig
from .models import RuleType


class CategoryClassifier:
    def __init__(self, config: CodeRulePatternConfig) -> None:
        self.config = config

    def classify(
        self,
        text: str,
        mentions: list[LabelMention],
        *,
        heading: str = "",
        heading_mentions: list[LabelMention] | None = None,
    ) -> RuleType:
        scores: Counter[str] = Counter()
        for mention in mentions:
            category = self.config.category_labels.get(mention.label_code)
            if category:
                scores[category] += 4
        for mention in heading_mentions or []:
            category = self.config.category_labels.get(mention.label_code)
            if category:
                scores[category] += 5

        haystack = f"{heading}\n{text}".casefold()
        for label_code, category in self.config.category_labels.items():
            stem = label_code.removesuffix("_convention")
            if stem and stem in haystack:
                scores[category] += 1

        if not scores:
            return RuleType.GENERAL
        return RuleType(scores.most_common(1)[0][0])
