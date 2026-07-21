import re

from .models import RequirementLevel


class RequirementClassifier:
    _rules = (
        (RequirementLevel.PROHIBITED, re.compile(r"禁止|不得|不允许|严禁|杜绝|不能")),
        (
            RequirementLevel.MANDATORY,
            re.compile(
                r"必须|应当|应(?:使用|采用|添加|包含|遵循)|需要|均需|需严格|"
                r"统一(?:使用|采用|添加|封装|存放)|所有"
            ),
        ),
        (RequirementLevel.RECOMMENDED, re.compile(r"建议|推荐|宜|尽量|优先|酌情")),
        (RequirementLevel.OPTIONAL, re.compile(r"可以|可选|按需")),
    )

    def classify(self, text: str) -> RequirementLevel:
        for level, pattern in self._rules:
            if pattern.search(text):
                return level
        if re.search(r"控制在\s*\d+|限制在\s*\d+|格式[:：]", text):
            return RequirementLevel.MANDATORY
        return RequirementLevel.UNKNOWN
