# ZYRelay DocIntelligence

ZYRelay DocIntelligence 是一个面向 PDF、DOCX 的规则优先文档智能 MVP。它把原始文档转换为可追溯的 MOM/SOM/BOM UOM Package，核心产物是基于治理标签的 `semantic_index`。0.3.0 将合同与团队代码规范能力封装为具有稳定 v1 契约的插件，并统一提供 Python、HTTP 和 CLI 三种入口。

Rule-first PDF/DOCX intelligence engine for structured extraction, semantic indexing, evidence tracing, and standardized Python, HTTP, and CLI integration.

## 范围与原则

- PDF：PyMuPDF 文本提取和可靠页码
- DOCX：python-docx 标题、Heading、段落、列表和表格逻辑块
- 标签：YAML 配置、正则优先、别名其次、可选模糊匹配
- 语义：label mentions、semantic index、简单实体和业务对象候选
- 代码规范：章节检测、强制程度/类别识别、简单规则表达式、正反例、证据验证
- LLM：默认关闭；失败不会影响规则结果
- 存储：本地文件系统和同目录临时文件原子替换

本项目不包含向量数据库、知识图谱、本体治理、复杂 RAG、多轮 Agent 或任务队列。

## 架构

```text
Upload
  → ValidateFile
  → ExtractDocument
  → BuildBlocks
  → NormalizeText
  → MatchLabels
  → BuildSemanticIndex
  → BuildSemanticCandidates
  → Optional LLMEnrichment
  → BuildConventionSections
  → ExtractConventionCandidates
  → ValidateConventionCandidates
  → BuildConventionIndex
  → BuildUOMPackage
  → SaveResult
```

数据目录：

```text
data/
├── documents/{document_id}/source.{ext}
├── doc_prepare/{document_id}/page-001.txt
├── doc_prepare/{document_id}/blocks.json
├── doc_index/{document_id}.json
├── plugin_executions/{execution_id}.json
└── plugin_artifacts/{execution_id}/{artifact_id}.json
```

`data/doc_index/{document_id}.json` 是完整且可独立校验的 UOM Package。

## 本地启动

要求 Python 3.11+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn zyrelay.app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

OpenAPI 文档位于 `http://127.0.0.1:8000/docs`。

## 标签配置

主标签文件是 `config/labels.yaml`。业务标签完全由 YAML 定义，不硬编码在匹配器中：

```yaml
labels:
  - code: contract_no
    name: 合同编号
    category: field
    value_type: string
    aliases: [合同编号, 合同号, 协议编号]
    patterns:
      - '(合同编号|合同号|协议编号)[：:\s]*([A-Za-z0-9_-]+)'
    description: 合同或协议的唯一编号
    ontology_uri: uom://som/ContractNumber
    business_object_type: Contract
    enabled: true
```

允许的 `category`：

- `document`
- `field`
- `entity`
- `relation`
- `event`
- `business_object`

`config/ground_truth/aliases.yaml` 可追加别名；`labels.yaml` 中的 `value_formats` 用于值格式校验。配置版本、标签配置哈希和业务对象配置哈希会写入每个 Package。

业务对象规则在 `config/business_objects.yaml`：

```yaml
business_objects:
  - type: Contract
    name: 合同
    ontology_uri: uom://bom/Contract
    required_labels: [contract_no, party]
    optional_labels: [amount, date, organization]
    min_required_matches: 2
```

规则只消费真实 mentions，不补全文档中不存在的属性，候选默认 `status=detected`。

### 团队代码规范配置

代码规范使用独立配置，避免污染合同标签：

- `config/code_convention_labels.yaml`：强制程度、规范类别、语言、框架、工具和示例标签
- `config/code_rule_patterns.yaml`：命名风格、目标对象和禁止调用规则
- `config/convention_profiles.yaml`：后续多文档团队 Profile 的预留配置

例如增加新的语言或检查工具，只需扩展标签别名；命名规则应集中写入
`code_rule_patterns.yaml`，不要散落在 Python 匹配代码中。

当前可解释规则表达式包括：

- PascalCase、camelCase、snake_case、UPPER_SNAKE_CASE、kebab-case
- 方法行数、单行字符数等上限
- 测试覆盖率等下限
- `System.out.println`、`Runtime.exec` 等明确禁止调用
- 公共方法文档注释要求
- 无明确阈值时生成 `unspecified_limit` 且 `executable=false`

所有候选都包含 block 内原文 offset。保存前会验证：

```text
block.text[start_offset:end_offset] == evidence_text
```

数值型规则的数值也必须逐字存在于证据中。

## 创建离线样例

```bash
python examples/create_sample_contract.py
```

该命令生成一个两页合同 PDF 和一个含表格的合同 DOCX。

## 上传 PDF/DOCX

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents \
  -F 'file=@examples/sample_contract.pdf'
```

同步 MVP 返回：

```json
{
  "document_id": "DOC-0123456789ABCDEF",
  "task_id": "TASK-0123456789ABCDEF",
  "status": "completed"
}
```

`document_id` 根据文件 SHA-256 稳定生成，同一内容重复上传得到相同 ID。

## 查询

读取标签语义索引：

```bash
curl http://127.0.0.1:8000/api/v1/documents/DOC-ID/semantic-index
```

按标签和文档查询：

```bash
curl 'http://127.0.0.1:8000/api/v1/search?label_code=contract_no&document_id=DOC-ID'
```

按规范化值过滤：

```bash
curl 'http://127.0.0.1:8000/api/v1/search?label_code=contract_no&value=HT-2026-001'
```

响应包含 `page_no`、`block_id`、block 内原文 offset、匹配原文、规范化值和置信度。

其他接口：

- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/blocks`
- `GET /api/v1/documents/{document_id}/labels`
- `GET /api/v1/documents/{document_id}/semantic-index`
- `GET /api/v1/documents/{document_id}/uom`
- `GET /api/v1/documents/{document_id}/code-conventions`
- `GET /api/v1/documents/{document_id}/convention-index`
- `GET /api/v1/conventions/search`

按规范类别、语言和强制程度查询：

```bash
curl 'http://127.0.0.1:8000/api/v1/documents/DOC-ID/code-conventions?category=naming&language=Java&requirement_level=mandatory'
```

查询可执行的覆盖率规范：

```bash
curl 'http://127.0.0.1:8000/api/v1/conventions/search?document_id=DOC-ID&keyword=覆盖率&executable=true'
```

## UOM Package 摘要

```json
{
  "schema_version": "1.0",
  "package_id": "PKG-...",
  "generated_at": "2026-07-18T00:00:00Z",
  "source": {},
  "mom": {
    "document": {},
    "blocks": []
  },
  "som": {
    "labels": [],
    "mentions": [],
    "semantic_index": {
      "contract_no": {
        "label_code": "contract_no",
        "documents": {
          "DOC-...": [
            {
              "block_id": "BLK-000001",
              "page_no": 1,
              "start_offset": 0,
              "end_offset": 21,
              "matched_text": "合同编号：HT-2026-001",
              "normalized_value": "HT-2026-001",
              "confidence": 0.95
            }
          ]
        }
      }
    },
    "raw_token_index": {},
    "candidates": [],
    "code_conventions": [],
    "convention_index": {
      "by_category": {},
      "by_language": {},
      "by_requirement_level": {},
      "by_tool": {},
      "by_document": {}
    }
  },
  "bom": {
    "business_objects": [],
    "team_convention_profiles": []
  },
  "processing": {
    "pipeline_version": "0.3.0",
    "ground_truth_version": "1.0.0",
    "label_config_hash": "...",
    "business_object_config_hash": "...",
    "steps": [],
    "warnings": [],
    "errors": []
  }
}
```

## 插件调用者指南

三种入口都调用 `DocIntelligencePlugin`，使用相同的 `PluginRequest`、校验、执行记录、错误码和 `PluginResponse`。默认同步执行、关闭 LLM，`execution_id` 为以后异步兼容预留。

### Python SDK

```python
from zyrelay.plugin import DocIntelligencePlugin
from zyrelay.plugin.contracts import PluginInput, PluginOptions, PluginRequest

plugin = DocIntelligencePlugin()
response = plugin.execute(
    PluginRequest(
        operation="process_document",
        input=PluginInput(
            source_type="file",
            file_path="examples/team_code_convention.docx",
            file_name="team_code_convention.docx",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        ),
        options=PluginOptions(
            mode="code_convention",
            output_detail="standard",
            enable_llm=False,
        ),
    )
)
assert response.status == "completed"
```

`summary` 只返回统计与 Artifact 引用；`standard` 返回文档、mentions、索引摘要、代码规范和业务对象；`full` 额外返回 blocks、标签、完整索引、UOM Package 与处理 trace。

### HTTP

发现插件及协议：

```bash
curl http://127.0.0.1:8000/api/v1/plugins
curl http://127.0.0.1:8000/api/v1/plugins/zyrelay.doc-intelligence/capabilities
curl http://127.0.0.1:8000/api/v1/plugins/zyrelay.doc-intelligence/schemas/input
```

multipart 上传：

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/plugins/zyrelay.doc-intelligence/execute-file \
  -F 'file=@examples/team_code_convention.docx' \
  -F 'mode=code_convention' \
  -F 'output_detail=standard' \
  -F 'enable_llm=false'
```

JSON 入口 `POST /api/v1/plugins/zyrelay.doc-intelligence/execute` 支持 `content_base64`。为防止任意文件读取，HTTP JSON 不接受服务器 `file_path`，也不会下载 `source_uri`。历史结果和 Artifact 只能通过受控 ID 获取：

```bash
curl http://127.0.0.1:8000/api/v1/plugins/zyrelay.doc-intelligence/executions/EXEC-ID
curl http://127.0.0.1:8000/api/v1/plugins/zyrelay.doc-intelligence/executions/EXEC-ID/artifacts
curl http://127.0.0.1:8000/api/v1/plugins/zyrelay.doc-intelligence/executions/EXEC-ID/artifacts/ART-ID
```

### CLI

```bash
python -m zyrelay.plugin manifest
zyrelay-plugin capabilities
zyrelay-plugin validate --file examples/team_code_convention.docx --mode code_convention
zyrelay-plugin execute \
  --file examples/team_code_convention.docx \
  --mode code_convention \
  --output-detail standard \
  --output result.json
```

退出码：`0` 成功、`2` 命令参数错误、`3` 输入校验失败、`4` 插件执行失败。

主要错误码包括 `missing_input`、`conflicting_input`、`unsupported_content_type`、`file_too_large`、`invalid_file`、`parse_failed`、`empty_document`、`configuration_error`、`execution_failed`、`result_not_found`、`artifact_not_found` 和 `internal_error`。错误响应不返回 traceback、密钥或内部文件路径。

## 插件开发者指南

- 插件运行配置位于 `config/plugin.yaml`；业务标签、业务对象与代码规则仍分别维护在原 YAML 中。
- wheel 会内置一份默认 YAML；源码运行优先读取仓库 `config/`，安装运行可通过 `ZYRELAY_*_CONFIG` 环境变量指向团队维护的外部版本。
- 对外 v1 DTO 位于 `zyrelay/plugin/contracts/`，不得导入 `zyrelay.app.models`；内部模型变化通过 Mapper 消化。
- 新增 PipelineStep、解析器、CandidateBuilder 或 Enricher 时继续在核心层实现，通过 `PluginDependencies` 注入，不在插件入口复制算法。
- 新 capability 同时更新能力提供器、manifest 和回归测试；改变字段语义时应新增 API 版本，不破坏 v1。
- `config_overrides` 只接受 `plugin.yaml` 白名单，不能覆盖 import 路径、存储目录或执行代码。
- 运行 `pytest` 执行原 API 与插件三入口的完整离线回归测试。

## LLM enrichment

默认配置：

```dotenv
ZYRELAY_LLM_ENABLED=false
ZYRELAY_LLM_BASE_URL=
ZYRELAY_LLM_API_KEY=
ZYRELAY_LLM_MODEL=
```

启用后只向 OpenAI-compatible `/chat/completions` 发送规则未覆盖的少量 blocks，并要求 JSON Schema 输出。候选必须引用有效 `block_id` 和逐字存在于原文的 evidence，置信度上限为 `0.80`。LLM 不能修改 blocks、mentions 或规则候选。

## 测试

```bash
pytest
```

测试不访问网络或外部模型，覆盖 PDF/DOCX、表格与顺序、正则/别名、offset、semantic index、业务对象规则、UOM 序列化、上传/查询、无效文件、空文档、扫描 PDF 检测和 LLM 关闭场景。

## 已知限制

- DOCX 文件本身通常不保存可靠的最终物理分页信息，因此 DOCX blocks 的 `page_no` 为 `null`；PDF 页码可靠。
- 图片型 PDF 只检测并标记 `requires_ocr=true`；MVP 默认的 OCRProvider 不执行 OCR。
- PDF Block 使用页面文本和空行切分，不恢复复杂多栏阅读顺序、表格结构或 bbox。
- PDF 中的规范标题、列表和代码示例仅使用文本启发式识别；复杂排版可能需要人工复核。
- 第一迭代只生成单文档规范候选，不执行代码扫描、AST 分析或外部静态分析工具。
- TeamConventionProfile、多文档去重和冲突检测尚未实现。
- 规范 LLM enrichment 尚未实现；现有通用 LLM enrichment 仍默认关闭。
- 模糊别名匹配默认关闭，避免不可解释的误报。
- 本地存储适合单机 MVP，不提供并发任务状态、权限、租户隔离和跨节点一致性。
- 业务对象只是证据驱动候选，不进行本体推理，也不会自动确认为事实。
