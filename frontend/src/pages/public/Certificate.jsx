import { useParams } from 'react-router-dom'
import { PublicShell, usePageTitle } from '../../components/Public'
import { Async, Err, useFetch } from '../../components/ui'
import { fmtDate } from '../../util'

const API = import.meta.env.VITE_API_URL || ''

export function VerifyCertificate() {
  usePageTitle('Verify a certificate')
  const { no } = useParams()
  const st = useFetch(`/certificates/${no}`)
  const d = st.data
  return (
    <PublicShell>
      <div className="form-card narrow">
        <h1 style={{ fontSize: '1.9rem' }}>Certificate check</h1>
        <p className="muted" style={{ margin: 0 }}>Certificate number <b>{no.toUpperCase()}</b></p>
        {st.loading && !d && <p>Checking…</p>}
        {st.error && !d && <div className="notice warn"><b>Not found.</b> We have no certificate with this number. Please check the number or ask the candidate for the link.</div>}
        {d?.valid && (
          <>
            <div className="notice info"><b>✓ Valid certificate</b></div>
            <dl className="kv"><dt>Holder</dt><dd><b>{d.holder}</b></dd><dt>Programme</dt><dd>{d.programme}</dd><dt>Issued by</dt><dd>{d.company}</dd>
              <dt>Grade</dt><dd>{d.grade} ({d.score}%)</dd><dt>Issued on</dt><dd>{fmtDate(d.issued_at)}</dd></dl>
          </>
        )}
        {d && d.found && !d.valid && <div className="notice warn"><b>This certificate has been revoked</b> and is no longer valid.</div>}
        <Err>{''}</Err>
      </div>
    </PublicShell>
  )
}

export function CertificatePage() {
  usePageTitle('Certificate')
  const { no } = useParams()
  const st = useFetch(`/certificates/${no}`)
  return (
    <PublicShell>
      <div className="page-w">
        <Async state={st}>
          {(d) => !d.valid ? <div className="notice warn" style={{ margin: 30 }}>This certificate is not valid.</div> : (
            <>
              <div className="row no-print" style={{ marginTop: 20 }}><button className="btn gold" onClick={() => window.print()}>Print or save as PDF</button></div>
              <section className="cert" aria-label="Certificate of completion">
                <div className="small muted" style={{ letterSpacing: '.2em', textTransform: 'uppercase' }}>{d.company}</div>
                <h1>Certificate of Completion</h1>
                <p>This is to certify that</p>
                <div className="name">{d.holder}</div>
                <p>has successfully completed the <b>{d.programme}</b> with grade <b>{d.grade}</b> ({d.score}%).</p>
                <div className="foot">
                  <div className="small"><div>Issued on {fmtDate(d.issued_at)}</div><div>Certificate no. <b>{d.cert_no}</b></div><div className="muted">Verify at /verify/{d.cert_no}</div></div>
                  <img className="qr" src={`${API}/api/certificates/${d.cert_no}/qr.svg`} width="110" height="110" alt={`QR code to verify certificate ${d.cert_no}`} />
                </div>
              </section>
            </>
          )}
        </Async>
      </div>
    </PublicShell>
  )
}
