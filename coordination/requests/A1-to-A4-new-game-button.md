# A1 -> A4: "New game" control on /play (humans asked, high priority)

Full spec in `coordination/COORDINATION.md` (section "procedural level generation").
Short: on `/play`, a New game control (difficulty 1-4, levels 3-8, optional seed, random
button) that calls A2's `POST /api/games/generate` and starts a session on the returned
`game_id`. Show the seed so people can share games. Until A2 ships the endpoint you can mock
it: any id of the form `gridworld-s{seed}-d{d}-l{n}-{hash}` comes back from the endpoint.
