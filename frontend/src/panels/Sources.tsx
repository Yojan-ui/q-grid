// "Where do these inputs come from?": a small "i" button that opens the replay's data_provenance list
// (scenario_<key>.json -> data_provenance: item, value_label, source, page, status). When the replay does not carry
// the list yet, it shows replay/data_status.json (what is real, what is pending) and a link to Verify.
import { useEffect, useState } from 'react'
import type { DataProvenanceRow } from '../lib/data'
import { regText } from '../lib/numcheck'
import { useDataStatus } from '../views/Views'

/** Ask the app to switch mode (App listens for this event), e.g. to open Verify's data section. */
export const gotoMode = (mode: string) => window.dispatchEvent(new CustomEvent('qgrid:mode', { detail: mode }))

const statusClass = (s: string) => (s === 'REAL' || s === 'EXISTING' || s === 'VERIFIED' ? 'okc' : 'pend')
const nice = (s: string) => s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ')

export function SourcesButton({ rows, label = 'Where these inputs come from' }: { rows?: DataProvenanceRow[] | null; label?: string }) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const f = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [open])
  return <>
    <button className="infobtn" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={label} title={label}>i</button>
    {open && <SourcesDialog rows={rows} onClose={() => setOpen(false)} />}
  </>
}

function SourcesDialog({ rows, onClose }: { rows?: DataProvenanceRow[] | null; onClose: () => void }) {
  const ds = useDataStatus()
  const has = !!rows && rows.length > 0
  return (
    <div className="modal" onClick={onClose} role="dialog" aria-modal="true" aria-label="data provenance">
      <div className="card sources" onClick={e => e.stopPropagation()}>
        <h3>Where the inputs come from</h3>
        {has ? <>
          <div className="tablewrap"><table className="tbl small"><thead><tr><th>Input</th><th>Value</th><th>Source</th><th>Status</th></tr></thead>
            <tbody>{rows!.map((r, i) => <tr key={`${r.item}-${i}`}><td>{r.item}</td><td className="tn">{regText(r.value_label, 'data_provenance value_label (replay text)')}</td>
              <td className="muted">{r.source}{r.page ? `, ${regText(r.page, 'data_provenance page (replay text)')}` : ''}</td>
              <td className={statusClass(r.status)}>{nice(r.status)}</td></tr>)}</tbody></table></div>
          <p className="muted small">From the replay (data_provenance, written by scripts/make_replay.py). Pending items are labelled stand-ins.</p>
        </> : <>
          <p className="small">This replay does not list a source for each input yet (data_provenance). What is real and what is still pending:</p>
          {ds ? <ul className="dslist small">{ds.items.map(i => <li key={i.key}><span>{i.label}</span><span className={i.real ? 'okc' : 'pend'}>{i.real ? 'Real' : nice(i.status)}</span></li>)}</ul>
            : <p className="small warn">replay/data_status.json is missing too (python scripts/data_status.py).</p>}
        </>}
        <div className="row">
          <button className="btn ghost small" onClick={() => { onClose(); gotoMode('verify') }}>Open Verify: data status</button>
          <button className="btn small" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}
