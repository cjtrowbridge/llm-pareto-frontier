# Host placeholder prompt

This pipeline's stages are deterministic (JSON regeneration, cost=min(rates),
dominance filter, HTML render) and invoke no model. This file exists so
`pipeline.yaml` can name a stage prompt and remains a valid host override point
if a future stage (e.g. frontier narrative, capability review) declares actual
`llm_justification` and is routed through the framework. Do not use an LLM
where deterministic logic is sufficient.