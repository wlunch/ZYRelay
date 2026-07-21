from zyrelay.app.conventions.config_repository import ConventionConfigRepository
from zyrelay.app.conventions.requirement_classifier import RequirementClassifier
from zyrelay.app.conventions.rule_expression_parser import RuleExpressionParser
from zyrelay.app.core.config import PROJECT_ROOT


def _parser() -> RuleExpressionParser:
    config = ConventionConfigRepository(
        PROJECT_ROOT / "config" / "code_rule_patterns.yaml"
    ).load()
    return RuleExpressionParser(config)


def test_requirement_levels() -> None:
    classifier = RequirementClassifier()
    assert classifier.classify("类名必须使用大驼峰") == "mandatory"
    assert classifier.classify("禁止直接捕获 Exception") == "prohibited"
    assert classifier.classify("建议公共方法添加 Javadoc") == "recommended"


def test_naming_and_numeric_rule_expressions() -> None:
    parser = _parser()
    naming = parser.parse("类名必须使用大驼峰命名")
    assert naming is not None
    assert naming.target == "class_name"
    assert naming.operator == "matches_regex"
    assert naming.parameters["style"] == "PascalCase"

    length = parser.parse("单个方法不得超过 80 行")
    assert length is not None
    assert length.target == "function_length"
    assert length.operator == "less_than_or_equal"
    assert length.expected == 80
    assert length.parameters["unit"] == "lines"

    coverage = parser.parse("单元测试覆盖率不得低于 80%")
    assert coverage is not None
    assert coverage.operator == "greater_than_or_equal"
    assert coverage.expected == 80
    assert coverage.parameters["unit"] == "percent"


def test_forbidden_call_and_unspecified_limit() -> None:
    parser = _parser()
    forbidden = parser.parse("禁止使用 System.out.println 输出日志")
    assert forbidden is not None
    assert forbidden.operator == "not_contains"
    assert forbidden.expected == "System.out.println"

    unspecified = parser.parse("方法长度不宜过长")
    assert unspecified is not None
    assert unspecified.operator == "unspecified_limit"
    assert unspecified.expected is None
    assert unspecified.executable is False


def test_camel_case_and_upper_snake_case_rules() -> None:
    parser = _parser()
    variable = parser.parse("变量与参数规范\n格式：小驼峰命名")
    assert variable is not None
    assert variable.target == "variable_name"
    assert variable.parameters["style"] == "camelCase"

    constant = parser.parse("常量规范\n格式：全部大写，单词之间用下划线分隔")
    assert constant is not None
    assert constant.target == "constant_name"
    assert constant.parameters["style"] == "UPPER_SNAKE_CASE"
