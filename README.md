# Huashu Art Motion for HiAgent

HiAgent-ready animation Skill for local file analysis and offline HTML video creation.

The Skill analyzes Excel and CSV data with the bundled DB-GPT csv-data-analysis engine, extracts text and provenance from PDF and Word files, and creates self-contained HTML animations with seven explainer grammars and four evidence presentation styles.

## Download for HiAgent

Download [dist/huashu-art-motion.zip](dist/huashu-art-motion.zip) and import the ZIP into HiAgent as a Skill. The archive contains one top-level huashu-art-motion/ directory.

The runtime is designed for network-restricted sandboxes. HTML output embeds its scripts, fonts, and supplied media. Excel statistics require compatible offline NumPy and pandas packages. PDF text extraction, DOCX text extraction, and animation building use bundled or standard-library components.

## Source

- Skill instructions: [huashu-art-motion/SKILL.md](huashu-art-motion/SKILL.md)
- Offline file analysis: [references/file-analysis.md](huashu-art-motion/references/file-analysis.md)
- Build and runtime guide: [references/hiagent-runtime.md](huashu-art-motion/references/hiagent-runtime.md)
- License notices for bundled code, fonts, and parsers are included with the Skill.

Based on the public alchaincyf/huashu-art-motion project. See its upstream revision and adaptation details in the Skill metadata and references.
