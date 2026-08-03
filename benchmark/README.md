# ZYRelay 可复现文档基准集

本目录提供 ZYRelay DocIntelligence 的离线、可审计基准框架。它覆盖代码规范、合同、企业制度、API 规范和图像型扫描件，验证从 PDF 解析到区块、规则、证据、provenance 与 OCR 模型记录的完整链路。

## 数据边界

- 数据源只在 `config/sources.yaml` 中配置；下载程序只接受 HTTPS 和该文件声明的官方域名。
- 当前清单包含 23 个案例：6 个代码规范、4 个合同、4 个企业制度、3 个 API 规范和 6 个由公开源生成的 image-only 扫描件。
- 原始 PDF、HTML、扫描件和运行结果是本地测试工件，已被 Git 忽略；仓库只版本化来源配置、清单、案例、脚本、审核结论和文档。
- `results/reports/source_audit.*` 给出来源、许可和本地/仓库使用结论。不得将私人文档、签字件、个人数据或来源条款不允许再分发的二进制文件提交到仓库。

## 环境与构建

Python 3.11+，并安装项目及可选 OCR 依赖。扫描件基线使用已缓存的 PaddleOCR；未安装或未配置 OCR 时，原生 PDF 基准仍可运行。

```bash
cd /Users/lunchw/Documents/Playground
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
# 可选：在隔离环境安装 OCR 依赖（首次模型部署遵守项目的离线策略）
.venv-paddleocr/bin/python -m zyrelay.models verify paddleocr
```

## 从来源重建数据集

所有命令均可重复执行，下载和 HTML 转 PDF 使用原子写入。仅在确认来源许可与网络策略允许时下载：

```bash
.venv/bin/python benchmark/scripts/download_dataset.py
.venv/bin/python benchmark/scripts/convert_html_to_pdf.py
.venv/bin/python benchmark/scripts/create_scanned_pdf.py \
  benchmark/sources/code_convention/google-java-style.pdf \
  benchmark/scanned/code_convention/BC-SCAN-001.pdf --quality clean --max-pages 3
.venv/bin/python benchmark/scripts/inspect_documents.py
.venv/bin/python benchmark/scripts/build_manifest.py
.venv/bin/python benchmark/scripts/source_audit.py
.venv/bin/python benchmark/scripts/validate_dataset.py
```

`create_scanned_pdf.py` 会把每页渲染为图片后重新嵌入 PDF，不保留原文字层，并会验证 PyMuPDF 提取文本为空。扫描变体和质量等级由 `config/benchmark.yaml` 管理。

## 执行和复现基线

本地模式直接调用 Relay；HTTP 模式调用已启动服务的 `/api/v1/relay/process`。每个案例保存原始 Relay 返回、UOM、ground、资源计划、模型记录、provenance、指标和评估，路径均相对化。

```bash
# 全量本地基线
.venv-paddleocr/bin/python benchmark/scripts/run_benchmark.py --baseline

# 单案例与扫描套件
.venv-paddleocr/bin/python benchmark/scripts/run_benchmark.py --case-id BC-SCAN-001 --baseline
.venv-paddleocr/bin/python benchmark/scripts/run_benchmark.py --suite scanned_document --baseline

# 汇总独立运行的案例；支持断点续跑后重新汇总
.venv-paddleocr/bin/python benchmark/scripts/finalize_results.py --output benchmark/results/baseline

# HTTP 模式
.venv/bin/python benchmark/scripts/run_benchmark.py --http --relay-url http://127.0.0.1:8000 --suite code_convention

# 比较 latest 与 baseline；语义回归会以非零状态退出
.venv/bin/python benchmark/scripts/compare_results.py
```

每个 case 文件位于 `cases/<类别>/<BC-ID>.yaml`。当前采用局部标注：结构、OCR、证据与 provenance 是硬性检查；业务规则、关键词和 convention 命中可按案例逐步补充 `expected_mentions` 与 `expected_rules`，避免把未审核内容作为“真值”。

## 输出与判定

`results/<run>/summary.json` 包含 Relay 版本、Git revision、Python/平台、输入哈希、模型版本、总耗时和逐案例结果。单案例目录结构如下：

```text
results/baseline/BC-SCAN-001/
├── relay_result.json
├── uom.json
├── ground.json
├── resources.json
├── models.json
├── provenance.json
├── metrics.json
└── evaluation.json
```

评估项包括处理成功、最小 block 数、约定候选最小数、证据与 provenance 完整性、block 顺序，以及扫描件的 OCR 运行、非空文本和 bbox。`compare_results.py` 会报告预期召回、证据、provenance 和耗时变化；预期召回/证据/provenance 下降判为回归，耗时增长仅告警。

## 维护规则

新增来源必须先更新 `config/sources.yaml`，记录官方 URL、发布方、许可、语言、期望特征和再分发判断，然后重建 manifest、case、source audit，并通过 `pytest tests/benchmark -q`。严禁在脚本中写死临时下载 URL，严禁跳过来源审核。
