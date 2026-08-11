# ZYRelay DocIntelligence 使用说明

本说明面向第一次使用 ZYRelay 的同事。即使不了解 Python、OCR 或大模型，也可以按照下面的步骤完成一次文档上传、关键词提取和原文追溯。

ZYRelay 可处理 PDF 和 DOCX 文档。它会把文档拆成可阅读的文本块，按照配置识别合同编号、金额、日期、单位等标签，并把每个结果关联回页码、文本块和原文位置。对扫描型 PDF，可选用本地 OCR 补充识别。

## 1. 先了解两种使用方式

| 方式 | 适合谁 | 能做什么 | 推荐程度 |
| --- | --- | --- | --- |
| Swagger 网页 | 非技术人员、演示人员 | 在浏览器中上传、查询、查看 JSON 结果 | **首次使用推荐** |
| HTTP 接口 | 需要和其他系统集成的人员 | 用程序或 `curl` 自动上传和查询 | 集成时使用 |
| 命令行插件 | 本地批量或脚本使用者 | 直接处理一个文件并保存 JSON | 熟悉终端后使用 |

第一次使用时，请优先打开 Swagger 网页，不需要记忆接口地址和参数。

## 2. 使用前准备

### 2.1 准备软件

需要安装：

- Python 3.11 或更高版本；
- Git（如果从代码仓库获取项目）；
- 一个待处理的 `.pdf` 或 `.docx` 文件。

在 macOS 或 Linux 的终端进入项目目录后执行：

```bash
cd /Users/lunchw/Documents/Playground
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

说明：首次安装会下载 Python 依赖。完成后，后续每次只需执行 `source .venv/bin/activate` 激活环境即可。

### 2.2 启动服务

仍在项目目录和已激活的虚拟环境中，执行：

```bash
uvicorn zyrelay.app.main:app --reload
```

如果终端出现类似以下内容，说明服务已启动：

```text
Uvicorn running on http://127.0.0.1:8000
```

不要关闭这个终端。打开浏览器并访问：

<http://127.0.0.1:8000/docs>

也可在另一个终端检查服务：

```bash
curl http://127.0.0.1:8000/health
```

返回 `status` 正常即可继续。

### 2.3 不使用本机 Python 的替代方式

如果已安装 Docker，也可在项目目录执行：

```bash
docker compose up --build
```

然后同样访问 <http://127.0.0.1:8000/docs>。

## 3. 最简单的操作：上传并提取标签

以下操作在 Swagger 网页完成。

1. 打开 <http://127.0.0.1:8000/docs>。
2. 找到 **POST `/api/v1/documents`**，点击该行展开。
3. 点击 **Try it out**。
4. 在 `file` 位置点击“选择文件”，选择 PDF 或 DOCX。
5. 点击 **Execute**。
6. 在 Response body 中记录 `document_id`，例如：

```json
{
  "document_id": "DOC-20260810-ABC123",
  "task_id": "TASK-20260810-DEF456",
  "status": "completed"
}
```

`document_id` 是后续查看结果的凭据。请复制保存它。

> 提示：当前 MVP 同步处理文件，返回 `completed` 表示基础处理已结束。若返回错误，请先检查文件是否为 PDF/DOCX、是否损坏，以及文件大小是否超过服务配置限制。

## 4. 如何查看处理结果

上传成功后，仍在 Swagger 页面中使用以下接口。点击接口、点击 **Try it out**、填入 `document_id`、点击 **Execute** 即可。

| 想查看的内容 | 接口 | 说明 |
| --- | --- | --- |
| 文档基本信息 | `GET /api/v1/documents/{document_id}` | 文件名、页数、解析器、是否需要 OCR、处理状态 |
| 文档分块 | `GET /api/v1/documents/{document_id}/blocks` | 文本按页和段落拆分后的 block，按 sequence 排序 |
| 已识别的标签 | `GET /api/v1/documents/{document_id}/labels` | 合同编号、金额、日期等命中及其证据 |
| 语义索引 | `GET /api/v1/documents/{document_id}/semantic-index` | 以 `label_code` 聚合的可检索索引 |
| 业务对象 | `GET /api/v1/documents/{document_id}/business-objects` | 如合同对象候选；默认是 detected，不是人工确认结论 |
| 完整结果包 | `GET /api/v1/documents/{document_id}/uom` | 一份完整的 UOM JSON，可交给下游系统 |

### 4.1 怎样理解“标签结果”

在 `labels` 返回结果中，一个 `mention` 表示一次可定位的标签命中。重点看以下字段：

```json
{
  "label_code": "contract_no",
  "matched_text": "合同编号：HT-2026-001",
  "normalized_value": "HT-2026-001",
  "page_no": 1,
  "block_id": "BLK-000001",
  "start_offset": 0,
  "end_offset": 16,
  "confidence": 0.95,
  "match_method": "regex"
}
```

- `label_code`：系统使用的标准标签代码，例如 `contract_no` 表示合同编号；
- `matched_text`：命中的原文；
- `normalized_value`：清洗后的可使用值；
- `page_no`：原文页码；
- `block_id`：所在文本块；
- `start_offset` / `end_offset`：该文本在原始 block 文本中的字符位置；
- `confidence`：置信度；规则正则命中通常是 `0.95`；
- `match_method`：识别方法，如 `regex`、`alias_exact`、`alias_fuzzy` 或 `llm`。

因此，ZYRelay 给出的不是只含关键词的列表，而是“关键词 + 原文证据 + 页面位置”的结果。

## 5. 如何追溯一个关键词回原文

以查询合同编号为例：

1. 先调用 `GET /api/v1/search`。
2. 在 `label_code` 填写 `contract_no`。
3. 在 `document_id` 填写上传时取得的文档 ID。
4. 点击 Execute。

系统返回的每一项都会给出页码、block ID、字符位置、命中原文和置信度。随后调用 `GET /api/v1/documents/{document_id}/blocks`，在返回内容中找到相同的 `block_id`，即可阅读这一段完整原文。

对外部系统而言，可直接调用：

```bash
curl 'http://127.0.0.1:8000/api/v1/search?label_code=contract_no&document_id=DOC-20260810-ABC123'
```

如果还想按具体值过滤，可增加 `value`：

```bash
curl 'http://127.0.0.1:8000/api/v1/search?label_code=contract_no&document_id=DOC-20260810-ABC123&value=HT-2026-001'
```

## 6. 使用 Relay 增强流程（需要模型记录或规范识别时）

普通文档提取使用 `/api/v1/documents` 即可。若需要查看 GroundChoose、资源计划、模型执行记录、OCR 决策或代码规范候选，请使用 **POST `/api/v1/relay/process`**。

在 Swagger 中，建议第一次保持以下默认值：

- `enterprise_id`：`default`
- `environment`：`dev`
- `mode`：`code_convention`（处理一般文档也可使用）
- `enable_ocr`：`true`
- `enable_layout_model`：`false`
- `enable_llm`：`false`
- `output_detail`：`standard`

选择文件后点击 Execute。返回中会包含 `execution_id`。可继续查询：

| 接口 | 作用 |
| --- | --- |
| `GET /api/v1/relay/executions/{execution_id}` | 本次 Relay 执行的总体记录 |
| `GET /api/v1/relay/executions/{execution_id}/ground` | 本次选择的标签、规则和 Ground 配置 |
| `GET /api/v1/relay/executions/{execution_id}/resources` | ResourcePlan：计划使用和实际使用的资源 |
| `GET /api/v1/relay/executions/{execution_id}/models` | 每个模型的执行/跳过、版本、耗时与回退情况 |
| `GET /api/v1/relay/provenance/{provenance_id}` | 某条结果的完整追溯链 |

对于一般业务使用者，建议先以 `/api/v1/documents` 验证标签和页码追溯；只有需要说明“本次是否调用 OCR 或小模型”时，再使用 Relay 接口。

## 7. 扫描 PDF 与 OCR 的使用方法

扫描 PDF 是指 PDF 页面没有可复制的文字，内容本质上是一张张图片。系统会先检测这种情况，再决定是否调用 OCR；不会对每一份 PDF 都做 OCR。

使用 OCR 前请确认：

1. 已创建并安装 PaddleOCR 专用环境；
2. PaddleOCR 模型已经预置到 `data/model_cache/paddleocr/`；
3. 执行验证命令返回 `verified: true`。

```bash
.venv-paddleocr/bin/python -m zyrelay.models verify paddleocr
```

上传扫描 PDF 时，在 Relay 接口保留 `enable_ocr=true`。若 OCR 插件可用，输出 block 会有页码、位置框和置信度；若插件未就绪，系统会标记需要 OCR 并记录 warning，不会把虚构内容当作 OCR 结果输出。

## 8. 命令行使用（可选）

如果不想启动服务，也可以用插件命令处理本地文件：

```bash
source .venv/bin/activate
zyrelay-plugin validate --file /完整路径/合同.docx
zyrelay-plugin execute --file /完整路径/合同.docx --output /完整路径/结果.json
```

说明：

- `validate` 只检查文件是否可以处理；
- `execute` 执行处理；
- `--output` 指定结果 JSON 的保存位置；不指定时结果会打印到终端；
- `--mode auto` 是默认模式；
- `--enable-llm` 仅在已完成相关配置时使用，普通使用不需要打开。

查看插件能力：

```bash
zyrelay-plugin manifest
zyrelay-plugin capabilities
```

## 9. 常见问题

### Q1：上传后没有识别出合同编号、金额或日期？

先在 `blocks` 中确认原文是否被正确提取。如果原文存在但没有标签，检查 `config/labels.yaml` 中是否有对应别名或正则。业务标签由配置驱动，不应直接修改 Python 代码。

### Q2：为什么扫描 PDF 没有文字结果？

通常是 PaddleOCR 插件未完成安装或本地模型缓存未就绪。请执行 `verify paddleocr`。系统会保留 `requires_ocr=true` 和 warning，避免把未识别内容误报为结果。

### Q3：关键词能否定位到“第几行”？

文本型 PDF/DOCX 的精确追溯单位是“页码 + block + 字符偏移量”；因为不同阅读器的视觉换行可能不同，系统不把显示行号作为稳定主键。扫描 PDF OCR 还会提供位置框（bbox），可用于在页面图片中定位。

### Q4：模型没有安装，系统还能用吗？

可以。基础 PDF/DOCX 解析、规则标签、semantic_index、业务对象候选和 UOM 输出不依赖可选模型。模型不可用时会执行 fallback，并在处理结果中说明原因。

### Q5：模型识别结果是否可以直接当作正式结论？

不建议。模型主要用于辅助元数据和候选发现。合同编号、金额等关键业务字段应优先查看规则命中与原文证据；业务对象候选默认状态为 `detected`，仍需人工审核或后续业务流程确认。

### Q6：处理文件保存在哪里？

默认保存在项目的 `data/` 目录：

```text
data/documents/{document_id}/     原始上传文件
data/doc_prepare/{document_id}/   解析页文本和 blocks（若保留）
data/doc_index/{document_id}.json 最终 UOM Package
```

## 10. 配置标签的最简单方法

标签配置位于 `config/labels.yaml`。新增标签时复制一个现有标签，填写标签代码、中文名称、别名和正则。例如：

```yaml
- code: project_no
  name: 项目编号
  category: field
  value_type: string
  aliases: [项目编号, 项目号]
  patterns:
    - '(项目编号|项目号)[：:\\s]*([A-Za-z0-9_-]+)'
  description: 项目的唯一编号
  enabled: true
```

保存后重启服务，再上传文档验证。建议先用少量样本确认页码、原文证据和误匹配情况，再把标签用于正式业务流程。

## 11. 推荐的日常操作顺序

1. 启动服务；
2. 打开 `/docs`；
3. 上传一份 PDF/DOCX；
4. 记录 `document_id`；
5. 查看 `labels` 和 `semantic-index`；
6. 使用 `/search` 查询一个标签，核对页码与原文；
7. 需要扫描件或模型执行说明时，改用 `/relay/process`；
8. 对关键结果进行人工复核后，再交给下游系统使用。

这样可以先获得稳定、可解释的规则结果，再按需要启用 OCR 和其他模型能力。
