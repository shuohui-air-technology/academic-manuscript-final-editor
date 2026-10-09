# Academic Manuscript Final Editor — User Guide

[中文](README.md)

A final-stage editing skill for academic manuscripts. Intended use: **final-stage editing** of a manuscript whose scientific content is already stable — infer writing preferences from the supplied editorial feedback, search the whole draft for analogous problems, revise the prose without changing protected scientific content, and synchronize bilingual versions.

Not intended for: drafting new papers, choosing scientific methods, external literature verification, or layout-only work (citation-format reordering, margins, and so on).

## Package structure

```
academic-manuscript-final-editor/
├── SKILL.md                             # skill body (the agent's core instructions)
├── README.md                            # this guide (Chinese)
├── README.en.md                         # this guide (English)
├── agents/openai.yaml                   # agent interface configuration (display name, default prompt, implicit-invocation policy)
├── references/editorial-style-rules.md  # editorial decision rules for whole-manuscript revision
└── scripts/
    ├── scan_manuscript_style.py         # locates style candidates (locates only, never edits files)
    └── check_scan_dispositions.py       # builds the itemized disposition skeleton and self-checks before validation
```

Runtime dependency: Python 3.9+ (standard library only, no third-party packages).

## Installation

Put the whole `academic-manuscript-final-editor/` folder into your agent's skills directory:

- **Codex CLI**: `~/.codex/skills/academic-manuscript-final-editor/`
- **Other agent frameworks compatible with the SKILL.md convention**: their own skills directory (keep the directory name identical to the skill `name`)

Restart the agent session after installation. The skill supports implicit invocation (`allow_implicit_invocation: true` in `agents/openai.yaml`), so it triggers when your request matches its description; you can also call it by name explicitly.

## Usage

### Three working modes

| Mode | Trigger | Behaviour |
|---|---|---|
| **Revise** | you authorize a candidate revision | produces a separate candidate; after the protected checks pass, waits for your decision on applying it |
| **Audit** | you only want a review, diagnosis, or issue list | read-only; outputs an issue list |
| **Learn** | you supply comments or tracked changes | infers the smallest rule behind each change and classifies its scope |

### Standalone invocation examples

```text
使用 academic-manuscript-final-editor 审查这份已完成实质修订的稿件，
找出全文同类表达问题，并列出需要统一的地方。
```

```text
Use academic-manuscript-final-editor to audit this substantively revised draft,
find analogous expression problems throughout it, and list the needed corrections.
```

### Invocation by mode

```
# Revise mode: apply the editorial feedback
这是我的论文和审阅批注,请按批注全文修订,并检查同类问题。

# Audit mode: issue list only
帮我通读手稿,列出所有风格和一致性问题,先不要改文件。

# Learn mode: infer rules from tracked changes
这是我带修订记录的文件,请推断每条修改背后的写作规则、
标注每条规则的作用域(段落级/章节级/项目级/跨项目可复用),
不要动原文件。

# Bilingual synchronization
中文版是我最近手工修订的权威版本,请先完成中文,
再按语义(而非逐词)同步英文版。
```

### Deliverables

Every whole-manuscript task ends with a compact summary: the files changed, the editorial rules inferred with their scopes and the analogous locations handled, confirmation that protected scientific content was checked, unresolved scientific or editorial questions, and (when applicable) render and independent-review status.

## Style scanning script

`scripts/scan_manuscript_style.py` locates style-review candidates in Markdown / plain text / DOCX (internal workflow residue, repeated defensive statements, and so on). **The script only locates candidates** — every finding needs your own editorial judgement.

In the JSON output each finding carries a `finding_id` (a content fingerprint derived from path/line/rule_id/evidence that the validator recomputes itself); the final-edit receipt requires one decision (accept/reject/defer/not_applicable) with its evidence per finding.

DOCX scanning only covers the body text inside `word/document.xml` and marks `coverage_status: main-document-text-only` in the JSON. Comments, tracked changes, fields, headers and footers, footnotes, text boxes, and layout must be checked by the document workflow and a per-page render receipt; this scanner's output is not a substitute.

```bash
# Basic use: scan one or more files and print a human-readable report
python3 scripts/scan_manuscript_style.py manuscript.md

# Machine-readable JSON (for an agent or pipeline)
python3 scripts/scan_manuscript_style.py --json manuscript.docx

# Add protected scientific terms (repeatable)
python3 scripts/scan_manuscript_style.py \
    --protected-term "非负" --protected-term "zero catch" manuscript.md

# Change the context length shown per finding (default 70 characters)
python3 scripts/scan_manuscript_style.py --context 100 manuscript.md

# For CI: exit non-zero when a high-severity finding is present
python3 scripts/scan_manuscript_style.py --fail-on high manuscript.md
```

Final editing requires **an itemized disposition**: every reported finding carries a `finding_id`, and the disposition record must give one decision and its evidence per finding.

```bash
# Build the skeleton (covers every finding_id; decisions and evidence left open)
python3 scripts/check_scan_dispositions.py --scan editorial_scan.json \
    --template-out editorial_scan_dispositions.json

# After filling it in, self-check before validation (decision vocabulary, evidence
# references, one-to-one IDs, consistent counts, hash binding)
python3 scripts/check_scan_dispositions.py --scan editorial_scan.json \
    --dispositions editorial_scan_dispositions.json
```

## Keeping the manuscript's meaning while revising

Final editing mainly improves expression, organization, and consistency, and it also checks whether an edit changes the research meaning.

- **Improve expression, verify the scientific content.** Revise long, repeated, or vague sentences, and check numbers, units, equations, citations, and conclusions against the original. For example, "there is a correlation" must keep its meaning and must not be polished into "causes"; "no significant difference was found" must also be preserved intact.
- **Keep the original and provide a comparable revision.** Edits are made in a separate candidate so you can review the differences, choose which changes to adopt, and restore the earlier version. Submitted or formally reviewed manuscripts keep their historical versions.
- **Handle citation numbering separately.** After deleting one citation, the remaining citations and bibliography entries keep their original numbers first. If renumbering is needed, it is handled consistently per your confirmed request.
- **Check that the Chinese and English versions say the same thing.** Finish the revision in the language designated for this round first, then synchronize the other version and check that conclusions, limitations, numbers, and citations correspond. When both manuscripts contain independent edits and it is unclear which is authoritative, confirm with you first.
- **Clean up editing-process records mixed into the body.** Keep notes such as "which round of checks has been completed" in the working record, so the manuscript text focuses on the research; process descriptions required by a study protocol, preregistration, or audit report are still kept.

The complete editing rules are in [SKILL.md](SKILL.md) and the [editorial rules reference](references/editorial-style-rules.md).
