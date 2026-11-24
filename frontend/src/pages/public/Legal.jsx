import { useParams } from 'react-router-dom'
import { PublicShell, usePageTitle } from '../../components/Public'
import { Async, useFetch } from '../../components/ui'
import { fmtDate } from '../../util'

export default function Legal({ slug: fixed }) {
  const params = useParams()
  const slug = fixed || params.slug
  const st = useFetch(`/legal/${slug}`)
  usePageTitle(st.data?.document.title || 'Legal')
  return (
    <PublicShell>
      <div className="legal">
        <Async state={st}>
          {({ document: d }) => (
            <>
              <h1>{d.title}</h1>
              <p className="small muted">Version {d.version} · published {fmtDate(d.published_at)}</p>
              {d.body.split('\n\n').map((para, i) => <p key={i}>{para}</p>)}
            </>
          )}
        </Async>
      </div>
    </PublicShell>
  )
}
