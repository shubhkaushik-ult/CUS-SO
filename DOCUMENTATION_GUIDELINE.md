# Documentation Protocol & Future Maintenance Guidelines

This document defines the standard operating procedures and mandatory templates for maintaining documentation in the **CUS SO & FnV Sales Order Automation Platform**.

---

## 🎯 Core Directive

Whenever any developer or AI assistant makes changes to this codebase, discovers a new edge case, or alters an architectural pattern, **the corresponding documentation files MUST be updated immediately as part of the task completion.**

---

## 📁 Repository Documentation Map

All documentation is located in the root directory:

| Document Path | When to Update |
| :--- | :--- |
| [`README.md`](file:///d:/CUS%20SO/README.md) | When new core modules, endpoints, supported cities, or top-level prerequisites are introduced. |
| [`ARCHITECTURE.md`](file:///d:/CUS%20SO/ARCHITECTURE.md) | When modifying database queries, system flows, API routes, or adding new components. |
| [`ERROR_LOG_AND_EDGE_CASES.md`](file:///d:/CUS%20SO/ERROR_LOG_AND_EDGE_CASES.md) | When encountering a new runtime error, edge case, rate limit, or adding a fallback mechanism. |
| [`CHANGELOG.md`](file:///d:/CUS%20SO/CHANGELOG.md) | **Every PR / release / feature update** must append an entry under `[Unreleased]` or the new version tag. |
| [`DB_Lookup_and_Output_Formats.md`](file:///d:/CUS%20SO/DB_Lookup_and_Output_Formats.md) | When altering MySQL lookup queries, table joins, or output CSV column header mappings. |
| [`Institutional_Format_Changes.md`](file:///d:/CUS%20SO/Institutional_Format_Changes.md) | When modifying Institutional SO specific column mappings, default values, or data types. |

---

## 📝 Maintenance Protocols & Templates

### 1. Documenting a Code Change (Updating `CHANGELOG.md`)

When adding a feature, fixing a bug, or changing default behavior, append an entry to [`CHANGELOG.md`](file:///d:/CUS%20SO/CHANGELOG.md) using this format:

```markdown
## [Version/Date] - Brief Feature Title

### Added
- Description of new features, endpoints, or utility functions.

### Changed
- Description of modified default values, refactored modules, or updated schemas.

### Fixed
- Description of bug fixes or edge case handling.
```

---

### 2. Documenting a New Error or Edge Case (Updating `ERROR_LOG_AND_EDGE_CASES.md`)

When discovering a new error, bug, API quota limit, or data anomaly:
1. Add an entry to the **Troubleshooting Matrix** in [`ERROR_LOG_AND_EDGE_CASES.md`](file:///d:/CUS%20SO/ERROR_LOG_AND_EDGE_CASES.md):

```markdown
| **E<XX>** | `Error / Log Pattern Snippet` | Root cause description | Impact on system | Automated / Manual Solution |
```

2. If it is a complex edge case, add a detailed section under **Detailed Edge Case Analysis**:

```markdown
### 3.X [Edge Case Name]
- **Symptom**: What happens when the edge case occurs.
- **Root Cause**: Why it occurs (e.g. data format mismatch, database record ambiguity).
- **Solution / Workaround**: How the code handles it or how developers should resolve it.
```

---

### 3. Documenting an Architectural Change (Updating `ARCHITECTURE.md`)

If you add a module, API route, or change a database query:
1. Update the **Mermaid Architecture Diagram** in [`ARCHITECTURE.md`](file:///d:/CUS%20SO/ARCHITECTURE.md) if component interactions changed.
2. Update the **Component Description** or **Database Schema & Query Specifications** section.
3. Update the **API Routes Specification** table if new routes were added.

---

## ✅ Post-Edit Verification Checklist

Before completing any development or documentation task, verify:
- [ ] Are all relative file links in markdown formatted with clickable `file:///` links?
- [ ] Has [`CHANGELOG.md`](file:///d:/CUS%20SO/CHANGELOG.md) been updated with the change rationale?
- [ ] If an error was fixed, is it recorded in [`ERROR_LOG_AND_EDGE_CASES.md`](file:///d:/CUS%20SO/ERROR_LOG_AND_EDGE_CASES.md)?
- [ ] Do code snippets in documentation match the actual implementation in Python?
