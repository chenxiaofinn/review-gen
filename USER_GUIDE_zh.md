# review-gen 中文用户指南

本文档面向个人本地使用，说明 `review-gen` 能做什么、如何按步骤运行，以及 API key、邮箱等环境信息应该放在哪里。

## 1. 这个项目能做什么

`review-gen` 是一个面向管理学、战略、创业、创新、组织研究等方向的文献综述工作流工具包。它不是一个网页应用，而是一组 Python 脚本、内置 MCP 后端和综述写作技能，核心目标是把“零散检索 + 临时问 AI”变成可复用、可审计的综述流水线。

主要功能：

- 按 ABS/AJG 期刊等级，通过 OpenAlex 检索高质量英文文献。
- 将多轮检索结果合并为一个去重的主文献库。
- 生成筛选表，记录文献是否纳入、是否需要全文、排除原因和备注。
- 根据筛选结果生成全文下载清单。
- 按 DOI 增量下载可获取的论文 PDF。
- 把手动收集或自动下载的 PDF 通过 MinerU 转成 Markdown。
- 将 Markdown 分块，便于后续检索证据和辅助写作。
- 生成综述计划、写作包和引用白名单。
- 在交付前审计草稿中的 DOI，降低幻觉引用风险。

## 2. 本地项目路径

当前本地部署路径：

```powershell
D:\AIProgram\paper-review-project\review-gen
```

进入项目并启用虚拟环境：

```powershell
cd D:\AIProgram\paper-review-project\review-gen
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 拦截脚本执行，可先在当前窗口临时放宽策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. 推荐工作区结构

每个综述主题建议使用一个独立工作区。项目脚本会自动创建固定目录：

```text
01_search/      检索原始结果和导出文件
02_corpus/      合并后的主文献库
03_screening/   标题摘要筛选表、证据表
04_fulltext/    全文清单、PDF 收件箱、PDF 归档、MinerU 配置
05_mineru/      MinerU 返回的原始包和解析结果
06_chunks/      Markdown 分块索引
07_plan/        综述计划和历史版本
08_outputs/     写作包、草稿、引用白名单、审计报告
```

建议把你的工作区放到项目下的 `review-workspaces/`，例如：

```powershell
$REVIEW_GEN = "D:\AIProgram\paper-review-project\review-gen"
$WORKSPACE = "$REVIEW_GEN\review-workspaces\ai-agents-review"
```

`review-workspaces/` 已加入 `.gitignore`，不会被提交到 GitHub。

## 4. 一条完整操作流程

下面是一条从零开始的推荐流程。把示例中的主题、检索词和字段替换成你的研究问题即可。

### 4.1 初始化工作区

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  init-workspace `
  --topic "AI agents and organizational decision making"
```

初始化后重点看这几个文件：

- `$WORKSPACE\review_config.json`
- `$WORKSPACE\03_screening\screening_table.csv`
- `$WORKSPACE\04_fulltext\mineru.env.example`

### 4.2 检索 ABS/AJG 文献

按 ABS/AJG 字段检索，例如信息管理领域：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\openalex_ajg_bridge.py" `
  search-abs `
  --query "AI agents organizational decision making" `
  --field "INFO MAN" `
  --min-rank "4" `
  --year-start 2018 `
  --limit 100 `
  --format json `
  --output-path "$WORKSPACE\01_search\raw_json\ai_agents_info_man_4plus.json"
```

如果不确定领域，`--field ""` 可以覆盖所有 ABS/AJG 期刊：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\openalex_ajg_bridge.py" `
  search-abs `
  --query "generative AI strategy organization" `
  --field "" `
  --min-rank "3" `
  --year-start 2018 `
  --limit 200 `
  --format json `
  --output-path "$WORKSPACE\01_search\raw_json\genai_all_3plus.json"
```

常用字段示例：

- `INFO MAN`：信息管理
- `STRAT`：战略
- `ORG STUD`：组织研究
- `INNOV`：创新
- `ENT-SBM`：创业与中小企业管理
- `MKT`：营销
- `HRM&EMP`：人力资源与雇佣研究

### 4.3 合并检索结果

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  merge-search-results
```

输出重点：

- `$WORKSPACE\02_corpus\master_corpus.jsonl`
- `$WORKSPACE\02_corpus\master_corpus.csv`
- `$WORKSPACE\03_screening\screening_table.csv`

### 4.4 人工筛选标题和摘要

打开：

```text
$WORKSPACE\03_screening\screening_table.csv
```

重点填写这些列：

- `included_title_abstract`：是否纳入，填 `yes` 或 `no`
- `exclusion_reason`：排除原因
- `need_full_text`：是否需要全文，填 `yes` 或 `no`
- `screening_notes`：简短备注

建议先只让真正相关、需要深入阅读的文献进入全文阶段，不要默认下载所有 PDF。

### 4.5 生成全文清单

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  prepare-fulltext-manifest `
  --min-priority medium `
  --require-included
```

输出文件：

```text
$WORKSPACE\04_fulltext\fulltext_manifest.csv
```

### 4.6 自动下载 PDF

如果只是预览会下载哪些论文：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\download_manifest_papers.py" `
  --workspace "$WORKSPACE" `
  --min-priority high `
  --max-papers 10 `
  --dry-run
```

确认后实际下载：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\download_manifest_papers.py" `
  --workspace "$WORKSPACE" `
  --min-priority high `
  --max-papers 10 `
  --parallel 3 `
  --email "your-email@university.edu"
```

下载成功的 PDF 会进入：

```text
$WORKSPACE\04_fulltext\pdf_inbox\
```

自动下载覆盖不到的文献，可以手动下载后放入同一个目录。建议文件名：

```text
YEAR__FirstAuthor__ShortTitle.pdf
```

### 4.7 配置 MinerU 并转换 PDF

初始化工作区后会生成示例文件：

```text
$WORKSPACE\04_fulltext\mineru.env.example
```

复制一份为：

```text
$WORKSPACE\04_fulltext\mineru.env
```

然后填入你的 MinerU token：

```env
MINERU_API_KEY=your-token-from-mineru
MINERU_API_BASE_URL=https://mineru.net
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=en
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_IS_OCR=false
```

运行转换：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  convert-pdfs-with-mineru `
  --env-path "$WORKSPACE\04_fulltext\mineru.env"
```

转换后的 Markdown 通常在：

```text
$WORKSPACE\05_mineru\extracted\
```

成功转换后，PDF 会被归档到：

```text
$WORKSPACE\04_fulltext\pdf_archive\
```

### 4.8 生成 Markdown 分块

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  chunk-markdown
```

输出：

```text
$WORKSPACE\06_chunks\chunk_index.jsonl
```

可以按问题检索相关片段：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  retrieve-chunks `
  --query "How do AI agents affect organizational decision making?" `
  --purpose finding `
  --top-k 8 `
  --include-neighbors `
  --format markdown
```

### 4.9 生成综述计划

```powershell
python "$REVIEW_GEN\skills\management-review-planner\scripts\build_review_plan.py" `
  --workspace "$WORKSPACE" `
  --topic "AI agents and organizational decision making" `
  --word-count 3000 `
  --language zh `
  --top-papers-mode dynamic `
  --top-papers 0
```

输出：

```text
$WORKSPACE\07_plan\review_plan.md
```

重要规则：正式写作前，先人工阅读并确认 `review_plan.md`。项目设计上要求“先批准计划，再写正文”。

确认计划后可记录批准状态：

```powershell
python "$REVIEW_GEN\skills\review-orchestrator\scripts\review_state_manager.py" `
  approve-plan `
  --workspace "$WORKSPACE" `
  --approved-by "chenxiaofinn" `
  --note "Framework approved for drafting."
```

### 4.10 生成写作包和引用白名单

```powershell
python "$REVIEW_GEN\skills\management-review-writer\scripts\build_review_packet.py" `
  --workspace "$WORKSPACE" `
  --topic "AI agents and organizational decision making" `
  --top-papers-mode dynamic `
  --top-papers 0 `
  --output-path "$WORKSPACE\08_outputs\review_packet.md"
```

重点输出：

- `$WORKSPACE\08_outputs\review_packet.md`
- `$WORKSPACE\08_outputs\review_guardrails.md`
- `$WORKSPACE\08_outputs\citation_allowlist.jsonl`

### 4.11 草稿引用审计

把你的草稿放到：

```text
$WORKSPACE\08_outputs\review_draft.md
```

然后运行：

```powershell
python "$REVIEW_GEN\skills\management-review-writer\scripts\validate_draft_citations.py" `
  --workspace "$WORKSPACE" `
  --draft-path "$WORKSPACE\08_outputs\review_draft.md"
```

审计重点：

- 草稿中的 DOI 是否存在于 `citation_allowlist.jsonl`
- DOI 是否能通过 Crossref/OpenAlex 解析
- 可选严格模式下，作者-年份引用是否匹配

## 5. API key 和环境信息配置在哪里

### 5.0 推荐：一次性全局配置

如果你不想每个综述工作区都手动配置一次，可以在项目根目录下的 `config` 文件夹中创建：

```text
D:\AIProgram\paper-review-project\review-gen\config\.env.local
```

内容示例：

```env
MINERU_API_KEY=your-token-from-mineru
MINERU_API_BASE_URL=https://mineru.net
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=en
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_IS_OCR=false
PAPER_DOWNLOAD_EMAIL=your-email@university.edu
OPENALEX_API_KEY=your-openalex-api-key
OPENALEX_EMAIL=your-email@university.edu
```

现在 `init-workspace` 会自动检测`config\.env.local`。如果它存在，且新工作区还没有 `04_fulltext\mineru.env`，脚本会自动复制生成：

```text
<review-workspace>\04_fulltext\mineru.env
```

如果某个工作区已经有自己的 `mineru.env`，脚本不会覆盖它。这样你可以保留一份全局默认配置，同时允许单个项目单独调整语言、OCR、公式和表格解析设置。

你的真实密钥文件应放在 `config` 目录下，例如 `config\.env.local` 和 `config\API_KEY.txt`。它们都已加入 `.gitignore`。注意：`.venv` 是 Python 虚拟环境文件夹，不要把配置文件放进 `.venv` 里面。
### 5.1 MinerU API Key

用途：把 PDF 转成 Markdown。

配置位置：

```text
<review-workspace>\04_fulltext\mineru.env
```

必填项：

```env
MINERU_API_KEY=your-token-from-mineru
```

可选项：

```env
MINERU_API_BASE_URL=https://mineru.net
MINERU_MODEL_VERSION=vlm
MINERU_LANGUAGE=en
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_IS_OCR=false
```

注意：

- 不要把真实 `mineru.env` 提交到 GitHub。
- 初始化工作区生成的是 `mineru.env.example`，需要你复制成 `mineru.env` 后再填 token。
- 中文 PDF 可将 `MINERU_LANGUAGE=zh`，扫描版 PDF 可尝试 `MINERU_IS_OCR=true`。

### 5.2 论文下载邮箱

用途：给 Unpaywall 等开放获取解析服务使用。

推荐方式是在命令里传：

```powershell
--email "your-email@university.edu"
```

也可以在当前 PowerShell 窗口设置环境变量：

```powershell
$env:PAPER_DOWNLOAD_EMAIL = "your-email@university.edu"
```

兼容旧变量名：

```powershell
$env:SCIHUB_CLI_EMAIL = "your-email@university.edu"
```

一般不建议把邮箱写入仓库文件。如果你想长期配置到系统环境变量，可用 Windows 系统环境变量界面设置 `PAPER_DOWNLOAD_EMAIL`。

### 5.3 OpenAlex

当前 `review-gen` 已接入 OpenAlex API key。把 OpenAlex key 放在 `config\.env.local` 的 `OPENALEX_API_KEY` 中，运行 `openalex_ajg_bridge.py` 检索时会自动作为 `api_key` 参数传给 OpenAlex API。OpenAlex 官方提供免费 API key，带 key 的免费额度高于无 key 试用额度。可选的 `OPENALEX_EMAIL` 会作为 `mailto` 参数传给 OpenAlex，便于请求识别。

可选后端路径配置：

```powershell
$env:OPENALEX_AJG_MCP_ROOT = "D:\path\to\openalex-ajg-mcp"
```

通常不需要设置。当前项目已内置：

```text
backend\openalex-ajg-mcp
```

### 5.4 paper-download-mcp 后端路径

当前项目已内置下载后端：

```text
backend\paper-download-mcp
```

通常不需要设置。如果你想替换为自己的下载后端，可设置：

```powershell
$env:PAPER_DOWNLOAD_MCP_ROOT = "D:\path\to\paper-download-mcp"
```

### 5.5 下载输出目录

通过 `download_manifest_papers.py` 运行时，PDF 默认进入当前工作区：

```text
<review-workspace>\04_fulltext\pdf_inbox\
```

`PAPER_DOWNLOAD_OUTPUT_DIR` 主要用于直接作为 MCP 服务运行 `paper-download-mcp` 时的默认下载目录。正常使用本项目 workflow 时一般不需要设置。

## 6. 中文文献怎么放

如果你从 CNKI 或其他中文数据库导出了 RIS 文件，放到：

```text
<review-workspace>\02_corpus\cnki_ris\
```

然后在生成计划或写作包时，相关脚本会读取这些 RIS 记录。写作包默认会把中文 RIS 文献加入引用白名单；如果不想加入，可在 writer 脚本中使用：

```powershell
--exclude-cn-ris-in-allowlist
```

## 7. Git 使用方式

当前本地仓库建议这样维护：

- `origin`：你的 fork，`https://github.com/chenxiaofinn/review-gen.git`
- `upstream`：原作者仓库，`https://github.com/harrylee0412/review-gen.git`
- 当前个人适配分支：`personal-adaptations`

查看状态：

```powershell
git status
git remote -v
```

提交个人修改：

```powershell
git add .
git commit -m "docs: update local user guide"
git push
```

从原作者同步更新时，建议先拉取 upstream，再决定是否合并：

```powershell
git fetch upstream
git log --oneline --decorate --graph --all -20
```

## 8. 常见问题

### 没有找到 `fulltext_manifest.csv`

先运行：

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  prepare-fulltext-manifest
```

### 没有 PDF 被下载

检查 `fulltext_manifest.csv` 中候选文献是否满足：

- `full_text_priority` 不低于命令里的 `--min-priority`
- `need_full_text` 是 `yes`
- `doi` 不为空
- 没有被已有 `pdf_status=ready` 跳过

可以先用 `--dry-run` 看候选列表。

### MinerU 报缺少 API key

检查是否存在：

```text
<review-workspace>\04_fulltext\mineru.env
```

并确认其中有：

```env
MINERU_API_KEY=your-token-from-mineru
```

运行转换时必须显式传：

```powershell
--env-path "$WORKSPACE\04_fulltext\mineru.env"
```

### 检索结果太少

可以尝试：

- 放宽 `--min-rank`，例如从 `4` 改为 `3`
- 不指定 `--field`，覆盖所有 ABS/AJG 期刊
- 增加 `--limit`
- 使用更宽泛的英文关键词
- 分多轮检索后再 `merge-search-results`

### 什么时候可以开始写正文

建议满足三点后再开始：

- `master_corpus.jsonl` 已生成
- `screening_table.csv` 已完成基本筛选
- `07_plan\review_plan.md` 已人工确认并批准

项目的核心纪律是：计划未确认，不进入正式写作；引用审计未通过，不作为最终稿交付。





## 可选：前沿文献推送工作流

前沿文献推送是工作区内的可选子流程，固定写入 `<review-workspace>\09_frontier_push\`，不会替代现有的检索、语料库、全文、计划和写作流程。候选文献先进入推送报告，只有你确认后，才通过 promotion 写入 `01_search\raw_json\`，再由原来的 `merge-search-results` 进入正式 corpus。

```powershell
python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  init-frontier-push

python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  draft-interest-profile `
  --intent "检索企业资产定价影响因素的相关文献"

python "$REVIEW_GEN\skills\openalex-ajg-insights\scripts\review_workflow.py" `
  --workspace "$WORKSPACE" `
  run-frontier-push `
  --profile firm_asset_pricing_determinants `
  --source-tiers A,C `
  --input "$WORKSPACE\09_frontier_push\source_records\records.json"
```

`InterestProfile` 使用 YAML，保存在 `09_frontier_push\profiles\`。其中 `directionality` 用来区分“X 的影响因素”和“X 的影响/经济后果”；默认不要把 X 作为解释变量的论文混入“X 的影响因素”。

LLM 功能使用 OpenAI 兼容配置：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。没有 key 时不会报错退出，而是写出可复制的 prompt fallback。论文拆解可用 `decompose-paper --paper-key <key>`，输出到 `09_frontier_push\deep_reads\`。