# review-gen 操作指南

## 第一部分：项目用途

本项目旨在节约文献检索、阅读和文献综述撰写的时间。它以原有的文献综述工作流为基础，并增加了一个可选的前沿文献推送子工作流。前沿推送用于发现指定年份和顶级期刊中的新文献，为论文选题提供灵感；确认后的文献可以接入完整综述流程。完整文献综述适用于确定研究方向后寻找研究缺口，也适用于论文主体完成后撰写文献综述部分。前沿推送默认面向指定年份内的 FT50、UTD24、ABS/AJG 4★等顶级期刊，不是任何最新论文。前沿产出不能直接进入正文，只有人工确认后的候选经过 promotion、合并 corpus、全文处理和综述计划后，才进入正式写作证据链。

## 一、确定检索意图

人工先确定 `directionality`：

```text
X 的 determinants / antecedents / factors
→ factors_of

X 的 effects / consequences / impact
→ effects_of

X 与 Y 的 relationship / association / correlation
→ descriptive

明确要求同时研究原因和结果
→ bidirectional
```

其中，`descriptive` 的多概念主题必须同时命中 X 和 Y 两组术语，不能只命中其中一方。

## 二、生成并审核 profile

### 1. LLM 生成 profile

LLM 根据研究意图生成：

```text
09_frontier_push/profiles/<profile-id>.yml
```

profile 主要包含：

```yaml
directionality:
target_construct:
exact_phrases:
near_phrases:
related_terms:
exclude_keywords:
required_concept_groups:
```

例如“重复劳动与员工满意度”会拆成：

```yaml
required_concept_groups:
  work_repetition:
    - work monotony
    - repetitive work
  employee_outcomes:
    - job satisfaction
    - employee well-being
```

For descriptive profiles, the existing profile fields compile into at most two
queries. The first uses exact phrases in every required concept group; the
second uses exact plus near phrases in every group. Terms inside a group are
joined with `OR`, and required groups with `AND`. No Cartesian product is
generated. `related_terms`, exclusions, directionality checks, and JEL codes
remain candidate-scoring or metadata fields.

### 2. LLM 审核 profile

审核结果保存为：

```text
09_frontier_push/profiles/<profile-id>.audit.yml
```

审核只提出建议，例如：

- 是否缺少真实学术术语；
- 是否混入过宽词；
- 两个概念组是否完整；
- directionality 是否正确。

### 3. 用户决定是否采纳

你可以选择：

```text
全部采纳
部分采纳
不采纳
```

在你确认前：

- 不修改 profile；
- 不开始正式检索。

确认后，Codex 根据你的决定修改：

```text
09_frontier_push/profiles/<profile-id>.yml
```

然后重新检查 profile 是否合格。

## 三、确定来源和年份

项目级筛选设置位于：

```text
09_frontier_push/frontier_settings.yml
```

默认内容是：

```yaml
source_ids:
  - abs3
year_start: 2025
year_end: 2026
limit_per_query: 100
```

这里控制：

- 检索哪些来源；
- 检索哪个年份范围；
- 每个关键词最多抓多少篇；
- 每条查询、每个 ISSN 分块最多抓多少篇。

profile 审核后先离线预览查询：

```text
python <review-gen-home>/skills/openalex-ajg-insights/scripts/review_workflow.py \
  --workspace <review-workspace> \
  preview-frontier-queries \
  --profile <profile-id>
```

确认查询表达式和预计请求数后，人工在 settings 中加入
`max_queries: 1` 或 `max_queries: 2`。缺失或超出可用轮数时，采集会在
调用 OpenAlex 前停止。旧工作区已有的 `max_queries` 继续有效。

新工作区默认来源是：

```text
ABS3
```

默认年份是：

```text
2025–2026
```

## 四、调用 OpenAlex 采集原始文献

根据 profile 和 settings 调用 OpenAlex。

原始检索结果保存到：

```text
09_frontier_push/source_records/
```

文件示例：

```text
abs_ajg_4star_<profile-id>_2025_2026.json
ft50_<profile-id>_2025_2026.json
utd24_<profile-id>_2025_2026.json
```

这些文件的作用是：

```text
记录本次实际从哪些来源、以什么年份范围、使用什么 profile 检索到了什么文献
```

它们是前沿检索的原始输入和追溯依据，不是正式 corpus。

## 五、生成候选和推送报告

对 `source_records/*.json` 进行：

- 去重；
- DOI 规范化；
- 排除 correction 等文献；
- 检查 directionality；
- 检查 `required_concept_groups`；
- 计算匹配分数；
- 按优先级排序。

运行结果保存到：

```text
09_frontier_push/runs/<run-id>/candidates.jsonl
```

这是机器可读的候选真值文件。

同时生成给人看的报告：

```text
09_frontier_push/reports/<profile-id>/<date>.md
```

报告包含：

- 标题；
- DOI；
- 来源期刊；
- candidate_id；
- 匹配分数；
- 推荐优先级；
- 命中术语；
- 推荐理由。

## 六、人工确认前沿候选

你对候选做三种决定：

```text
include
exclude
hold
```

决定记录到：

```text
09_frontier_push/runs/<run-id>/review_decisions.jsonl
```

例如：

```json
{
  "candidate_id": "fp_xxxxx",
  "decision": "include",
  "reason": "与研究主题直接相关"
}
```

这一步是前沿推送的人工闸门。

只有标记为 `include` 的候选，才能继续 promotion 和全文处理。

## 七、Promotion：生成主流程入口文件

对 `include` 候选执行 promotion，生成：

```text
01_search/raw_json/frontier_push_<run-id>.json
```

这个文件的作用是：

```text
把前沿候选转换成主流程可以读取的原始搜索结果格式
```

同时默认生成 Zotero 导入文件：

```text
02_corpus/zotero_ris/frontier_push_<run-id>.ris
```

注意：

```text
promotion 不会直接修改 master_corpus.jsonl
```

它只是提前生成一个“以后可以接入主流程”的文件。

因此，这一步不等于已经进入正式 corpus。

## 八、尝试下载前沿文献 PDF

下载对象是已经标记为 `include` 的候选。

系统优先尝试：

```text
OpenAlex
Unpaywall
```

成功下载的 PDF 保存到：

```text
04_fulltext/pdf_inbox/
```

下载记录保存到：

```text
09_frontier_push/runs/<run-id>/pdf_downloads.jsonl
```

下载失败的文献保存到：

```text
09_frontier_push/runs/<run-id>/manual_download.tsv
```

人工下载时，应按照 `manual_download.tsv` 中的 `expected_pdf_name` 命名，不应自行随意命名为 `fp_*.pdf`。系统之后依靠全文清单中的文件名匹配 PDF。

## 九、转换前沿 PDF 并生成前沿快报

前沿推送在这里形成一个相对完整的闭环：

```text
include 候选
→ PDF
→ MinerU Markdown
→ 前沿文献快报
```

### 1. MinerU 转换

前沿 PDF 通过 MinerU 转换，输出：

```text
05_mineru/extracted/<paper-directory>/full.md
```

同时更新：

```text
04_fulltext/fulltext_manifest.csv
```

清单中会记录：

- `paper_key`；
- PDF 文件名；
- PDF 路径；
- PDF 是否 ready；
- Markdown 是否 ready；
- Markdown 路径。

### 2. 生成前沿快报

基于这一批已转换的 Markdown 生成：

```text
09_frontier_push/briefs/<run-id>.md
```

快报采用固定格式，包含：

1. 批次信息；
2. 本期摘要；
3. 每篇文献的研究问题、方法、发现、贡献和局限；
4. 多篇文献的综合判断；
5. 后续研究启示；
6. 证据边界；
7. 输入文献和 Markdown 路径追溯。

因此，前沿推送在这一阶段已经可以独立完成：

```text
找到前沿文献
→ 人工确认
→ 获取全文
→ 转换 Markdown
→ 生成前沿快报
```

这份快报用于：

- 快速了解最新研究；
- 发现论文选题灵感；
- 比较多篇前沿文献；
- 提炼后续研究方向。

但它仍然不是正式综述正文，也不是正式引用白名单。

## 十、接入正式 corpus

前沿快报完成后，再把第七步生成的 promotion JSON 合并到主流程：

```text
01_search/raw_json/frontier_push_<run-id>.json
  ↓
merge-search-results
  ↓
02_corpus/master_corpus.jsonl
02_corpus/master_corpus.csv
```

这时前沿文献才正式进入综述语料库。

合并后会保留：

```text
paper_key
source_run_id
frontier_candidate_id
frontier_source_id
frontier_match_score
```

因此可以从正式 corpus 追溯回前沿运行。

## 十一、主流程中的 screening table

合并进入 corpus 后，系统生成或更新：

```text
03_screening/screening_table.csv
```

它不是前沿候选确认表，而是主综述筛选表。

典型字段包括：

```text
paper_key
included_title_abstract
need_full_text
exclusion_reason
screening_notes
```

前沿阶段的：

```text
include
```

表示：

```text
允许这篇文献进入主流程
```

主流程筛选表中的：

```text
included_title_abstract = yes
```

表示：

```text
这篇文献正式纳入当前综述研究
```

因此一篇前沿文献可能经历：

```text
前沿 include
→ promotion
→ master_corpus
→ screening table
→ included_title_abstract = yes
```

这不是重复设计，而是两个不同层级的判断。

## 十二、主流程全文清单和全文处理

前沿 PDF 已经下载并转换的文献，在进入主流程后可以被复用，不需要重复下载和转换。

主流程会根据正式 corpus 和 screening table 生成或更新：

```text
04_fulltext/fulltext_manifest.csv
```

它会检查：

- 哪些文献被标题摘要筛选纳入；
- 哪些文献需要全文；
- 哪些 PDF 已经存在；
- 哪些 Markdown 已经生成；
- 哪些文献仍然缺少 PDF 或 Markdown。

对于前沿阶段已经完成的文献：

```text
PDF ready
Markdown ready
```

系统直接复用。

对于主流程新增、但前沿阶段没有处理的文献，才需要：

```text
下载 PDF
→ MinerU 转换
→ 生成 Markdown
```

之后可继续生成：

```text
06_chunks/chunk_index.jsonl
```

用于后续检索和综述规划。

## 十三、前沿结果如何进入完整综述

完整的接入路径是：

```text
前沿 source_records
→ candidates.jsonl
→ 人工 include
→ promotion JSON
→ PDF 下载和前沿快报
→ merge-search-results
→ 02_corpus/master_corpus
→ 03_screening/screening_table
→ 04_fulltext/fulltext_manifest
→ 复用或补充 PDF
→ 05_mineru/extracted
→ 复用或补充 Markdown
→ 06_chunks
→ 07_plan/review_plan.md
→ 用户批准综述计划
→ 08_outputs 写作包和引用白名单
→ 综述正文
→ 引用审计
```

其中：

```text
09_frontier_push/briefs/
```

用于快速了解前沿，不直接绕过：

```text
master_corpus
screening table
全文处理
综述计划
引用白名单
```

最终可以把整个项目理解为两条路径：

```text
前沿文献推送：
profile
→ source_records
→ candidates
→ 人工确认
→ PDF/Markdown
→ frontier brief
```

以及：

```text
正式文献综述：
promotion
→ master_corpus
→ screening
→ fulltext
→ chunks
→ review_plan
→ writing
```
## 第二部分：新建项目和用户输入

用户提供研究主题并给出directionality。如果主题没有明确说明是directionality，则追加提问让用户确认 factors_of、effects_of、descriptive 还是 bidirectional。确认完成后系统创建对应主题工作区，如果该主题已经有的话，允许继续使用原有的工作区和旧材料。在每完成一个环节之后都需要向用户说明当前的进展，并引导用户继续下一环节。
我有点记不清楚全流程用户需要输入什么prompt，你帮我补充。

## 第二部分：新建项目和用户输入

用户首先提供：

```text
研究主题 + directionality
```

例如：

```text
主题：重复劳动与员工满意度
directionality：descriptive
```

如果主题没有明确说明 directionality，系统先追问：

```text
你想检索哪一类文献？

1. factors_of：X 的影响因素或前因
2. effects_of：X 的影响、后果或结果
3. descriptive：X 与 Y 的关系
4. bidirectional：同时检索 X 的影响因素和影响结果
```

确认后，系统创建对应的主题工作区，例如：

```text
review-workspaces/<project-id>/
```

工作区中会创建：

```text
09_frontier_push/
01_search/
02_corpus/
03_screening/
04_fulltext/
05_mineru/
06_chunks/
07_plan/
08_outputs/
```

如果该主题已经存在，系统先检查原工作区和旧材料，询问用户：

```text
发现已有工作区和历史材料。你希望：

1. 继续使用原工作区；
2. 基于原工作区创建新的检索运行；
3. 新建一个完全独立的工作区。
```

默认建议继续使用原工作区，但新的检索结果应保存为新的 `run_id`，不能覆盖旧运行记录。

## 全流程中用户需要输入的 Prompt

### 1. 新建项目

```text
新建文献研究项目。

主题：重复劳动与员工满意度
directionality：descriptive
```

如果不确定类型，可以只写：

```text
新建文献研究项目，主题是重复劳动与员工满意度。
```

系统会追加询问 directionality。

### 2. 生成检索 profile

```text
请根据该主题生成检索 profile，并说明双方概念分别覆盖哪些学术术语。
```

系统生成：

```text
09_frontier_push/profiles/<profile-id>.yml
```

### 3. 审核 profile

```text
请审核刚才生成的 profile，检查术语是否真实、是否过宽，以及 descriptive 是否同时覆盖两个概念。
```

系统生成：

```text
09_frontier_push/profiles/<profile-id>.audit.yml
```

### 4. 确认 audit 建议

系统汇报审核建议后，用户输入：

```text
全部采纳 audit 建议。
```

或：

```text
部分采纳：增加 job monotony，保留 employee well-being，不删除其他术语。
```

或：

```text
不采纳 audit 建议，保留原 profile。
```

确认后，系统才修改 profile 并继续检索。

### 5. 确认来源和年份

```text
新工作区默认使用 ABS3，年份范围 2025–2026；其他来源必须在工作区设置中显式增加。
```

如果要修改：

```text
来源使用 FT50 和 ABS/AJG 4★，年份范围改为 1990–2000。
```

设置保存到：

```text
09_frontier_push/frontier_settings.yml
```

### 6. 开始前沿检索

```text
使用已经确认的 profile 和当前来源设置，开始前沿文献检索。
```

系统会生成：

```text
09_frontier_push/source_records/
09_frontier_push/runs/<run-id>/candidates.jsonl
09_frontier_push/reports/<profile-id>/<date>.md
```

### 7. 确认候选

系统汇报候选后，用户可以输入：

```text
请将以下候选标记为 include：

fp_xxxxx
fp_yyyyy
```

或者：

```text
fp_xxxxx：include，直接相关
fp_yyyyy：hold，需要进一步查看
fp_zzzzz：exclude，与主题不相关
```

系统记录到：

```text
09_frontier_push/runs/<run-id>/review_decisions.jsonl
```

### 8. Promotion 和 PDF 下载

```text
对本次标记为 include 的候选执行 promotion，并尝试下载 PDF。
```

系统生成：

```text
01_search/raw_json/frontier_push_<run-id>.json
02_corpus/zotero_ris/frontier_push_<run-id>.ris
04_fulltext/pdf_inbox/
09_frontier_push/runs/<run-id>/pdf_downloads.jsonl
09_frontier_push/runs/<run-id>/manual_download.tsv
```

如果存在失败项，用户可以输入：

```text
我已经按照 manual_download.tsv 下载并放入指定目录，请继续检查全文文件。
```

### 9. 转换全文并生成前沿快报

```text
请对本次 include 文献执行 MinerU 转换，并生成固定格式的前沿文献快报。
```

系统生成：

```text
05_mineru/extracted/<paper-directory>/full.md
09_frontier_push/briefs/<run-id>.md
```

至此，前沿推送流程完成。

### 10. 将前沿结果接入主综述流程

如果用户希望继续写完整综述：

```text
请将本次已经确认的前沿文献接入主综述流程。
```

系统执行：

```text
merge-search-results
```

并生成或更新：

```text
02_corpus/master_corpus.jsonl
02_corpus/master_corpus.csv
03_screening/screening_table.csv
```

### 11. 主流程标题摘要筛选

```text
请根据当前综述主题，对 master corpus 生成标题摘要筛选建议。
```

系统提出建议后，用户集中确认：

```text
确认建议，将相关文献标记为 included_title_abstract=yes，
并将需要全文的文献标记为 need_full_text=yes。
```

### 12. 主流程全文处理

```text
请为已纳入综述的文献准备全文清单，并自动处理已有 PDF。
```

系统生成或更新：

```text
04_fulltext/fulltext_manifest.csv
05_mineru/extracted/
06_chunks/chunk_index.jsonl
```

缺失 PDF 仍然进入人工下载清单。

### 13. 生成综述计划

```text
请基于已筛选文献和全文 Markdown，生成综述计划。
```

系统生成：

```text
07_plan/review_plan.md
```

用户需要明确批准：

```text
我批准这份综述计划，可以继续生成写作包。
```

### 14. 生成写作包和正文

```text
请根据已批准的综述计划生成写作包、引用白名单和中文综述初稿。
```

系统生成：

```text
08_outputs/review_packet.md
08_outputs/review_guardrails.md
08_outputs/citation_allowlist.jsonl
review_draft.md
```

### 15. 引用审计

```text
请对综述初稿进行引用审计，检查 DOI、引用白名单和正文表述是否超出文献证据。
```

系统生成：

```text
citation_audit_report.md
```

整个用户操作原则可以概括为：

```text
用户只需要提供主题、确认检索类型、
确认 profile 修改、确认候选、
批准综述筛选结果和批准综述计划。
```

每完成一个环节，系统都应说明：

```text
当前完成了什么
生成了哪些文件
当前还缺什么
下一步建议做什么
是否需要用户确认
```

## 第三部分：开始正式检索前的确认

新建项目后不能直接开始 OpenAlex 检索，因为系统还不知道应该使用哪些学术术语、检索哪一种关系，以及文献来源和年份范围是什么。正式检索前，用户必须先确认两个内容：第一，经过审核和修订的关键词 profile；第二，期刊来源和年份设置。如果用户不修改，系统使用默认的 FT50、UTD24、ABS/AJG 4★和 2025–2026 年范围。

其中：

```text
关键词 profile
= 查什么、按什么关系查

来源和年份设置
= 去哪里查、查哪几年
```

这两个内容确认后，才开始调用 OpenAlex。

## 第四部分：候选确认

OpenAlex 检索完成后，系统会生成候选文献文件candidates，去重，根据相关度进行评分。用户需要进一步对候选文献标注，才能确定哪些文献需要下载。


> OpenAlex 检索完成后，系统会对原始文献进行去重、DOI 规范化和相关度评分，生成候选文献文件 `candidates.jsonl`，并生成供用户阅读的候选报告。用户需要对候选文献标注 `include / exclude / hold`，以确定哪些文献可以继续处理。只有标记为 `include` 的文献，才会进入 promotion，并由系统尝试下载 PDF；`exclude` 和 `hold` 文献不会继续下载。

主要产物是：

```text
09_frontier_push/runs/<run-id>/candidates.jsonl
09_frontier_push/reports/<profile-id>/<date>.md
09_frontier_push/runs/<run-id>/review_decisions.jsonl
```

## 第五部分：Promotion 与下载

对 `include` 文献执行 promotion 和 PDF 下载后，系统会生成pdf文件，下载失败会生成人工下载的文件。下载后的文献pdf都是以fp…….pdf来命名

对 `include` 文献执行 promotion 后，系统会生成主流程可读取的原始 JSON，并尝试下载 PDF。成功下载的 PDF 保存到 `04_fulltext/pdf_inbox/`；下载失败的文献会记录在人工下载清单中。人工下载时不能统一自行命名为 `fp_*.pdf`，应按照 `manual_download.tsv` 中的 `expected_pdf_name` 命名，否则后续全文清单可能无法自动匹配。
对应产物是：

```text
01_search/raw_json/frontier_push_<run-id>.json
02_corpus/zotero_ris/frontier_push_<run-id>.ris

04_fulltext/pdf_inbox/<expected_pdf_name>.pdf

09_frontier_push/runs/<run-id>/pdf_downloads.jsonl
09_frontier_push/runs/<run-id>/manual_download.tsv
```

这里的 `fp_...` 是 `candidate_id` 的形式，例如：

```text
fp_9157194ec319
```

它用于标识候选，不一定是 PDF 文件名。

## 第六部分：转换全文并生成前沿快报

PDF会通过Mineru转换为md文档，md文档进一步根据默认的模板来生成前沿文献推送简报。

> PDF 文件通过 MinerU 转换为 Markdown 文档，Markdown 文档保存到 `05_mineru/extracted/<paper-directory>/`。系统再根据固定的前沿快报模板，对本次已确认并完成转换的文献进行整理，生成前沿文献推送简报。简报保存到 `09_frontier_push/briefs/<run-id>.md`，至此本次前沿文献推送流程结束。

当前前沿推送流程到此为止：

```text
主题与 directionality
→ 生成并审核 profile
→ 确认来源和年份
→ OpenAlex 检索
→ 候选评分
→ include / exclude / hold
→ promotion
→ PDF 下载
→ MinerU 转 Markdown
→ 生成前沿文献推送简报
```

前沿推送操作指南暂时在这里截止，不继续展开它如何接入完整文献综述流程。
