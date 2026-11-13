# AfterQuery @ Junction 2026 — Challenge Brief

> Source: the official challenge description. Kept verbatim-in-substance as the core reference for every decision in this repo.

## The Challenge
Build a reinforcement learning environment that challenges today's best AI agents, demonstrate real failure modes, and show that its rewards reflect real progress.

## Introduction
Today's cutting-edge AI systems can solve Millennium Problems, discover new drugs, and create entire production apps with a few lines of prompting. But they still struggle in a wide variety of novel situations, ranging from everyday use cases to niche, highly technical workflows. We ask: what should AI agents be able to do that they still struggle with today?

At AfterQuery, we build environments for training and testing agents. The work starts with choosing a problem worth learning, defining an action and observation space, and defining a reward function that defines what success looks like. Getting those pieces right is a heavy research and engineering problem in itself.

For this challenge, we want to see your take on it. Build a world with something interesting to learn. Find out where strong agents struggle, and whether your reward actually encourages the behavior you intended.

## The challenge
Choose a setting you find interesting and build an environment an agent can interact with. It could be a game, a scientific simulation, a software task, a real-world process, or something we haven't thought of. Explain why you chose it and what an agent could learn there.

Your environment should have a clear goal, actions the agent can take, and a reward you can check. Run a frontier agent in it and compare the results with a stronger reference run your team can demonstrate and reproduce. We'll provide the agent harness and model credits.

Show where the agent falls short and why. The challenge should come from the decisions it needs to make, with access to the information and tools needed to succeed. We'll also try to find shortcuts that earn a high score without completing the task: reward hacking.

The setting and approach are yours to choose. We care about what makes the environment useful for learning and what your experiments reveal.

### Optional stretch goal
Train a smaller model using experience from your environment and show whether it improves.

## Prizes
Top three teams: €3,000, €1,500, €500. Winning team members can skip to the final stage of AfterQuery's interview process (work trial with the environments team). Finalists get AfterQuery gear.

## Judging rubric (100 p)
| Criterion | Pts | Full points | Zero points |
|---|---|---|---|
| **The gap** | 30 | Frontier agent consistently scores below a stronger reference run the team demonstrates; both reproducible across repeated runs. | No measurable gap, or gap can't be reproduced / checked against a demonstrated reference run. |
| **Meaningful difficulty** | 30 | Agent's main mistakes are explainable and tied to decisions in the task; the info and tools needed to do better are available to it. | Gap comes from unfairly withheld info, trick wording, impossible timing, or broken tools. |
| **Reward integrity** | 25 | Reward measures task success and survives judges' exploit attempts; doing nothing / stopping early earns little or nothing; doing the task well is the best way to score. | An exploit, loophole, or task-avoiding strategy beats successful play. |
| **Craft** | 15 | Rules and behavior make sense for the setting; judges run the eval from the README with **one command** and reproduce reported results. | Only works in the demo, or judges can't reproduce. |

## How judging runs
- 10-minute demo per team.
- Judges rerun with the standard harness: **reference run, three agent runs, a do-nothing baseline, and a stop-early baseline.**
- Judges spend **15 minutes hunting for reward exploits**.
- **Tiebreaker:** a smaller model shown improving after training on experience from the environment.

## Starting points (prompts, not requirements)
- Planning several steps ahead
- Exploring an unfamiliar system
- Using tools
- Managing limited resources
- Adapting when new information arrives

A small environment with a well-chosen challenge can be enough. Think about what better play looks like, how you'd measure it, and whether an agent could raise its score without getting better at the task.

## Resources provided
- Open-source agent harness: **Harbor running the OpenCode agent**, connecting to the environment **over MCP**
- Scoring skeleton
- Frontier model API credits per team (48 hours)
- On-site mentors: Daksh Raghuwanshi and Ved Vedere (AfterQuery environments team)
- Starter kit: harness docs + judging rubric
