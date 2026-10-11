# CODEX_INSTRUCTIONS.md

You are continuing an existing FPL-AI research project.

Before modifying code:

1. Read `README.md`.
2. Read `PROJECT_CONTEXT.md`.
3. Read `ARCHITECTURE.md`.
4. Read `ROADMAP.md`.
5. Inspect the complete current codebase.
6. Identify what is reusable and what should be replaced.
7. Do not immediately create another brute-force Wildcard optimizer.

The main lesson from V1–V5 is computational architecture, not insufficient filtering.

The next optimizer should be designed around MILP/ILP or another efficient constraint solver.

Do not silently rewrite the project's goals.

Do not remove useful existing data pipelines simply because the optimizer is being replaced.

When proposing changes:
- explain why
- keep modules small
- add tests
- benchmark performance
- preserve reproducibility
- avoid magic constants
- prefer measured improvements over added complexity

The project goal is a fast, explainable FPL decision engine, not a maximal-complexity model.

The AI layer should consume structured outputs from Python rather than attempting to reproduce numerical optimization itself.
