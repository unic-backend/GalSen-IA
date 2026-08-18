# SWE-agent — third-party notice

| | |
|---|---|
| Upstream | `https://github.com/SWE-agent/SWE-agent` |
| Licence | MIT |
| Copyright | © 2024 John Yang, Carlos E. Jimenez, Alexander Wettig, Shunyu Yao, Karthik Narasimhan, Ofir Press |
| Inspected | 2026-08-09 |
| What was taken | **Nothing.** No source code, no file, no fragment. |

## How GalSen IA uses it

`src/coding_engine/adapters/swe_agent_adapter.py` runs the `sweagent`
executable as a subprocess, installed in its own virtualenv
(`scripts/install_coding_engines.sh`). It is never imported.

The flags used come from the project's own command-line documentation:

    sweagent run
        --agent.model.name=<provider/model>
        --agent.model.api_base=<address>
        --agent.model.api_key=<key>
        --agent.model.per_instance_cost_limit=0
        --agent.model.total_cost_limit=0
        --agent.model.max_input_tokens=0
        --env.repo.path=<local repository>
        --problem_statement.text=<statement>

The three zeroed limits are required by the project for a self-hosted model:
cost accounting relies on the public litellm registry, which has no entry for
such models, and without them the run fails at start-up.

## Why subprocess and not a library

SWE-agent carries its own agent loop, its own tool layer and its own model
layer. Inside GalSen IA that would be a second Agent Runtime and a second Model
Engine beside the ones ADR-003 and the architecture overview define. Installing
it into the platform environment is worse still: the same experiment with aider
downgraded numpy and broke the Vision Engine, which is why every engine now
lives in its own virtualenv.

## Licence position

MIT permits use, modification and redistribution, and requires the copyright
notice to be preserved in copies of the software. **No copy is made here**, so
that obligation is not triggered; this notice exists for traceability.

Running a program as a subprocess creates no derivative work.

## Requirements and status

SWE-agent executes its agent in a container: **Docker is required**. The adapter
reports a missing Docker separately from a missing `sweagent`, because the two
call for different actions.

Upstream now states that `mini-SWE-agent` supersedes this project. That is
recorded in ADR-028: the adapter boundary is what would make swapping it cheap.
