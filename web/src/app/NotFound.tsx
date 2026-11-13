import { Link } from 'react-router-dom'
import { Empty } from '@/design/primitives'

export function NotFound() {
  return (
    <Empty action={<Link to="/play">Go to Play</Link>}>
      Nothing here. <span className="mono">{window.location.pathname}</span>
    </Empty>
  )
}
