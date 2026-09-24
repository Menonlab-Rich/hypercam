```markdown
# Agent Instructions & Project Guidelines

This file governs all AI agent interactions, code generation, refactoring, and documentation efforts within this repository. Adherence to these guidelines is mandatory.

---

## 1. Execution Defaults & Choice of Medium

When assigned a task without explicit implementation directives (e.g., when the choice of programming language, script vs. library, or tool selection is unspecified):

* **Default to Marimo Notebooks:** Prefer creating interactive, reactive Python notebooks using **Marimo** (`.py` notebook format).
* **Narrative Structure:** Interleave executable code cells with detailed, publication-ready Markdown cells to guide the reader step-by-step through the concept, methodology, implementation, and results.
* **Literate Programming:** Treat the notebook as a dynamic document where prose explains the context, mathematical theory, and reasoning, while the code demonstrates execution.

---

## 2. Code Authoring & Header Requirement

Every newly created or substantially modified code file or notebook (e.g., `.rs`, `.py`, `.cpp`, `.hpp`, `.m`, `.lua`, `.sh`) **MUST** begin with a standardized header at the very top of the file.

### Required Header Format

```text
==============================================================================
Author:        Richard G. Baird
Date Modified: [YYYY-MM-DD]
Notice:        This file was authored or modified with the assistance of 
               [Agent Tool / Model Name, e.g., Claude 3.7 Sonnet / Cursor Agent].
==============================================================================

```

*Adapt comment delimiters to match the target language syntax (e.g., `#` for Python/Bash, `//` or `/* */` for Rust/C++).*

---

## 3. Code Quality & Readability Standards

### A. Readability Over Cleverness

* **Prioritize Clarity:** Code must be explicit and legible. Avoid terse, overly dense "one-liners" or micro-optimizations that obscure intent.
* **Domain-Expert Accessibility:** Write code such that a domain expert (e.g., an optical engineer, physicist, or biologist) who is **not** a language expert can understand **what** the code is doing and, most importantly, **why**.
* **Self-Documenting Names:** Choose explicit, domain-meaningful variable and function names.
* *Good:* `exposure_time_milliseconds`, `focal_length_mm`, `compute_phase_mask_transmission()`
* *Bad:* `t`, `fl`, `calc()`


* **Domain Math Alignment:** When implementing mathematical models or algorithms, align variable names directly with established domain terminology or paper conventions (and document the mapping in comments).

### B. Dependencies & Standard Libraries

* **Leverage Existing Libraries:** Do not re-invent the wheel or roll custom implementations for solved problems (e.g., parsing, numerical linear algebra, data structures, matrix operations).
* **Use Standard & Community Packages:** Rely on mature, well-tested standard libraries or established third-party crates/packages before writing custom logic.

---

## 4. Documentation Requirements

Agents must maintain thorough, extensive, and complete documentation across all levels of the codebase.

### A. Narrative & Cell-Level Documentation (Notebooks)

* Use Markdown cells extensively to explain physical principles, math equations, assumptions, and interpretation of generated outputs or plots.

### B. Function & Module-Level Documentation

* **Functions & Types:** Every public function, struct, class, module, or method must include complete docstrings specifying intent, inputs, outputs, error conditions, and underlying mathematical/physical principles.
* **Inline Explanations:** Include inline comments explaining the **why** behind complex algorithms, parameter choices, physical constants, or boundary conditions.

### C. Module & Repository Documentation

* Maintain up-to-date `README.md` files at module/crate boundaries describing architectures, execution pipelines, prerequisites, and build steps.

---

## 5. Version Control & Commit Conventions

All commits made or suggested by the agent **MUST** follow the **Conventional Commits** standard (`v1.0.0`).

### Commit Message Format

```text
<type>(<scope>): <short descriptive summary in imperative mood>

[optional longer body explaining WHAT changed and WHY]

[optional footer(s)]

```

### Commit Types

* `feat`: A new feature or algorithm implementation.
* `fix`: A bug fix.
* `docs`: Documentation updates or docstring additions.
* `style`: Formatting, missing semicolons, line endings (no production code change).
* `refactor`: Restructuring code for readability without changing external behavior.
* `perf`: Changes aimed at improving execution speed or memory usage.
* `test`: Adding missing tests or correcting existing tests.
* `chore`: Build process, dependency updates, or tool configuration changes.

### Commit Guidelines

* Keep the summary line concise (≤ 72 characters) and written in the imperative mood (e.g., `feat(camera): add EVT3.0 frame header parsing`).
* Separate subject from body with a blank line when detailed rationale is required.

---

## 6. Agent Workflow Checklist

Before finishing any task, the agent must verify:

1. [ ] Check if execution directives were omitted; if so, confirm a Marimo notebook with rich Markdown cells was preferred.
2. [ ] File header is present and updated with author, current date, and agent/model details.
3. [ ] Variable names are descriptive and domain-appropriate.
4. [ ] Code uses existing standard/third-party libraries instead of bespoke routines.
5. [ ] In-line comments and docstrings explain the domain logic (**why**) alongside the code (**what**).
6. [ ] Proposed git commit messages adhere strictly to Conventional Commits.

```

<ElicitationsGroup message="Additional customizations you can add:">
  <Elicitation label="Include specific Marimo layout or reactive state guidelines" query="Update agent.md to add specific instructions on how to structure reactive state and UI elements in Marimo notebooks."/>
  <Elicitation label="Add formatting guidelines for equations and LaTeX rendering" query="Update agent.md to specify LaTeX and math formatting conventions for markdown cells."/>
</ElicitationsGroup>

```
