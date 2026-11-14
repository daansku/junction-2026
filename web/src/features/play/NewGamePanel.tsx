// "New game" on /play: asks the server to generate a fresh verified game from a seed
// (POST /api/games/generate, A1's engine via A2), then Play starts a run on it.
// Generation is CPU only on the server: no model call, so it is safe in published mode.
import { useState } from 'react'
import { api, HttpError } from '@/lib/api'
import { Button, Panel } from '@/design/primitives'

const DIFFICULTIES = [
  { d: 1, label: '1', title: 'easy' },
  { d: 2, label: '2', title: 'medium' },
  { d: 3, label: '3', title: 'hard' },
  { d: 4, label: '4', title: 'hardest: adds rules no model was trained on' },
]
const LEVELS = [3, 4, 5, 6, 7, 8]

/** seed / difficulty / levels from a game id like gridworld-s4217-d3-l6-1a2b3c4d. */
export function parseGameId(id: string | undefined) {
  const m = id?.match(/-s(\d+)-d(\d+)-l(\d+)(?:-|$)/)
  return m ? { seed: Number(m[1]), difficulty: Number(m[2]), levels: Number(m[3]) } : null
}

function explain(e: unknown) {
  if (e instanceof HttpError) {
    if (e.status === 404 || e.status === 405) return 'This server cannot generate games yet. Pick a game from the list for now.'
    if (e.status === 403) return 'That seed range is reserved for evaluation games. Try another seed.'
    if (e.status === 422 || e.status === 400) return 'The server rejected these settings. Check the seed and try again.'
  }
  return e instanceof Error ? e.message : String(e)
}

export function NewGamePanel({ onGenerated }: { onGenerated: (gameId: string) => void }) {
  const [difficulty, setDifficulty] = useState(2)
  const [levels, setLevels] = useState(6)
  const [seed, setSeed] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generate = async (useSeed: boolean) => {
    const n = seed.trim() === '' ? undefined : Number(seed)
    if (useSeed && n !== undefined && (!Number.isInteger(n) || n < 0)) {
      setError('A seed is a whole number, for example 4217.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const g = await api.generateGame({ difficulty, n_levels: levels, ...(useSeed && n !== undefined ? { seed: n } : {}) })
      if (!useSeed) setSeed('')
      onGenerated(g.game_id)
    } catch (e) {
      setError(explain(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel label="new game">
      <div className="newgame">
        <div className="newgame-row">
          <span className="kicker">difficulty</span>
          <div className="newgame-seg" role="group" aria-label="Difficulty">
            {DIFFICULTIES.map((x) => (
              <Button
                key={x.d}
                mono
                active={difficulty === x.d}
                aria-pressed={difficulty === x.d}
                title={x.title}
                onClick={() => setDifficulty(x.d)}
              >
                {x.label}
              </Button>
            ))}
          </div>
        </div>
        <label className="newgame-row">
          <span className="kicker">levels</span>
          <select value={levels} onChange={(e) => setLevels(Number(e.target.value))}>
            {LEVELS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="newgame-row">
          <span className="kicker">seed</span>
          <input
            type="text"
            inputMode="numeric"
            className="mono"
            value={seed}
            placeholder="random"
            onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, ''))}
            onKeyDown={(e) => e.key === 'Enter' && !busy && generate(true)}
          />
        </label>
        <div className="newgame-actions">
          <Button variant="primary" disabled={busy} onClick={() => generate(true)}>
            {busy ? 'Generating…' : seed ? 'Play this seed' : 'Generate'}
          </Button>
          <Button disabled={busy} onClick={() => generate(false)} title="Ignore the seed box and roll a new one">
            Random
          </Button>
        </div>
        {difficulty === 4 && <p className="muted newgame-note">Difficulty 4 adds rules no model was trained on.</p>}
        {error && (
          <p className="newgame-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </Panel>
  )
}
