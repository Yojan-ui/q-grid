// Small status badges for assets the replay marks as not yet on campus (campus.zones[i].asset_status,
// campus.cables_status). Text only: nothing is shown when the replay does not carry the field.
import type { AssetStatus } from '../lib/data'

const TITLE: Record<string, string> = {
  PROPOSED: 'Proposed: not on campus today; part of the plan being evaluated',
  PENDING: 'Pending: status not yet confirmed by RVCE',
}

export function StatusBadge({ s, what }: { s?: AssetStatus | null; what?: string }) {
  if (s !== 'PROPOSED' && s !== 'PENDING') return null
  return <span className={`pending proposed${s === 'PENDING' ? ' unconfirmed' : ''}`} title={`${what ? what + ': ' : ''}${TITLE[s]}`}>{s === 'PROPOSED' ? 'proposed' : 'unconfirmed'}</span>
}
