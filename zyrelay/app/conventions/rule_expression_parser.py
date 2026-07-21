from __future__ import annotations

import re

from .config_repository import CodeRulePatternConfig
from .models import RuleExpression, RuleOperator


class RuleExpressionParser:
    def __init__(self, config: CodeRulePatternConfig) -> None:
        self.config = config

    def parse(self, text: str) -> RuleExpression | None:
        clean = text.replace("**", "").replace("`", "")
        target = self._target(clean)

        style = self._naming_style(clean)
        if style and target:
            name, regex = style
            return RuleExpression(
                target=target,
                operator=RuleOperator.MATCHES_REGEX,
                expected=regex,
                parameters={"style": name},
                executable=True,
                tool_hint="custom_regex",
            )

        lower_bound = re.search(
            r"(?:不得|不能|不应)?(?:低于|少于)\s*(\d+(?:\.\d+)?)\s*(%|百分比)?",
            clean,
        )
        if lower_bound and target:
            return RuleExpression(
                target=target,
                operator=RuleOperator.GREATER_THAN_OR_EQUAL,
                expected=self._number(lower_bound.group(1)),
                parameters={"unit": "percent" if lower_bound.group(2) else "count"},
                executable=True,
                tool_hint="coverage" if "覆盖率" in clean else "ast",
            )

        upper_bound = re.search(
            r"(?:不得|不能|不应)?(?:超过|大于)\s*(\d+(?:\.\d+)?)\s*(行|字符|个字符|%)?",
            clean,
        ) or re.search(
            r"(?:控制在|限制在)\s*(\d+(?:\.\d+)?)\s*(行|字符|个字符|%)?(?:以内|以下)?",
            clean,
        )
        if upper_bound and target:
            unit = self._unit(upper_bound.group(2))
            return RuleExpression(
                target=target,
                operator=RuleOperator.LESS_THAN_OR_EQUAL,
                expected=self._number(upper_bound.group(1)),
                parameters={"unit": unit},
                executable=True,
                tool_hint="ast" if unit == "lines" else "line_length",
            )

        for item in self.config.forbidden_calls:
            if item.value in clean and re.search(r"禁止|不得|不允许|严禁", clean):
                return RuleExpression(
                    target=item.target,
                    operator=RuleOperator.NOT_CONTAINS,
                    expected=item.value,
                    executable=True,
                    tool_hint=item.tool_hint,
                )

        if re.search(r"硬编码.*(?:密码|密钥|Token|AppSecret)|(?:密码|密钥|Token|AppSecret).*硬编码", clean):
            return RuleExpression(
                target=target or "source_code",
                operator=RuleOperator.NOT_CONTAINS_SENSITIVE_SECRET,
                executable=False,
                tool_hint=None,
            )

        if target and re.search(r"必须.*(?:添加|包含)|均需.*(?:添加|包含)|建议.*添加", clean):
            expected = "Javadoc" if "Javadoc" in clean else "documentation_comment"
            return RuleExpression(
                target=target,
                operator=RuleOperator.REQUIRED,
                expected=expected,
                executable=True,
                tool_hint="ast",
            )

        if target and re.search(r"不宜过长|避免过长", clean):
            return RuleExpression(
                target=target,
                operator=RuleOperator.UNSPECIFIED_LIMIT,
                expected=None,
                executable=False,
            )
        return None

    def _target(self, text: str) -> str | None:
        hits: list[tuple[int, str]] = []
        for target, aliases in self.config.targets.items():
            for alias in aliases:
                index = text.find(alias)
                if index >= 0:
                    hits.append((index, target))
        return min(hits)[1] if hits else None

    def _naming_style(self, text: str) -> tuple[str, str] | None:
        for name, style in self.config.naming_styles.items():
            if any(alias.casefold() in text.casefold() for alias in style.aliases):
                return name, style.regex
        return None

    @staticmethod
    def _number(raw: str) -> int | float:
        value = float(raw)
        return int(value) if value.is_integer() else value

    @staticmethod
    def _unit(raw: str | None) -> str:
        if raw == "行":
            return "lines"
        if raw in {"字符", "个字符"}:
            return "characters"
        if raw == "%":
            return "percent"
        return "count"
