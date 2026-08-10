import re
from pathlib import Path

from pydantic import ValidationError

from zyrelay.app.core.config import load_yaml
from zyrelay.app.core.exceptions import LabelConfigInvalidError
from zyrelay.app.models import LabelDefinition


class LabelRepository:
    def __init__(self, label_path: Path, ground_truth_dir: Path) -> None:
        self.label_path = label_path
        self.ground_truth_dir = ground_truth_dir
        self._value_formats: dict[str, re.Pattern[str]] = {}

    def load(self) -> list[LabelDefinition]:
        try:
            raw = load_yaml(self.label_path)
            definitions = [
                LabelDefinition.model_validate(item) for item in raw.get("labels", [])
            ]
            if not definitions:
                raise ValueError("labels 列表为空")
            codes = [label.code for label in definitions]
            if len(codes) != len(set(codes)):
                raise ValueError("标签 code 重复")

            aliases_file = self.ground_truth_dir / "aliases.yaml"
            if aliases_file.exists():
                extra_aliases = load_yaml(aliases_file).get("aliases", {})
                definitions = [
                    label.model_copy(
                        update={
                            "aliases": list(
                                dict.fromkeys(
                                    label.aliases + extra_aliases.get(label.code, [])
                                )
                            )
                        }
                    )
                    for label in definitions
                ]

            gt_file = self.ground_truth_dir / "labels.yaml"
            formats = load_yaml(gt_file).get("value_formats", {})
            self._value_formats = {
                code: re.compile(pattern) for code, pattern in formats.items()
            }
            return [definition for definition in definitions if definition.enabled]
        except (OSError, ValueError, ValidationError, re.error) as exc:
            raise LabelConfigInvalidError(f"标签配置无效：{exc}") from exc

    def value_is_valid(self, label_code: str, value: str) -> bool:
        pattern = self._value_formats.get(label_code)
        return pattern is None or pattern.fullmatch(value.strip()) is not None
