# NOVEL-005 — Prompt Runtime & Model Provider

**Priority:** P0  
**Depends On:** NOVEL-001~004

## Goal

落地 Composable Prompt Architecture：

```text
System Policy
+ Agent Role
+ Task Template
+ Skills
+ Quality Profile
+ Context
+ Output Contract
→ Prompt Compiler
→ Model Adapter
→ Provider
```

## Must Implement

- PromptModule / metadata
- PromptRegistry
- dependency validation
- PromptCompiler
- PromptLineage
- TaskDefinitionRegistry
- Output Contract Generator
- ModelProfile / ModelRegistry
- ModelProvider interface
- Default Adapter
- Mock Provider refactor to same pipeline
- at least one real provider integration path
- RequirementSpec demo schema
- Requirement Agent demo prompt

## Critical Rules

- Prompt source = Git files
- Project data never stored in Prompt Library
- Prompt Compiler does not query Memory
- Provider-specific code isolated in providers/adapters
- same resolved input → stable prompt hash
- structured output revalidated by Pydantic
- secrets never enter logs / lineage
- real provider tests optional in CI

## Acceptance

必须证明：
- Prompt versions coexist
- stable resolves to exact version
- PromptLineage records exact modules
- Mock & real provider use same runtime path
- context/user content stays in lower-trust section
- provider errors map to unified errors
