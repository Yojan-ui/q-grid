// A KaTeX formula, with KaTeX (and its CSS / fonts) loaded only when a formula is first shown.
import { useEffect, useState } from 'react'

export function Tex({ src, className = 'formula' }: { src: string; className?: string }) {
  const [html, setHtml] = useState<string | null>(null)
  useEffect(() => {
    let off = false
    Promise.all([import('katex'), import('katex/dist/katex.min.css')]).then(([k]) => {
      if (!off) setHtml(k.default.renderToString(src, { throwOnError: false, displayMode: true }))
    })
    return () => { off = true }
  }, [src])
  return html ? <div className={className} dangerouslySetInnerHTML={{ __html: html }} /> : <div className={className} aria-busy="true"><code>{src}</code></div>
}
