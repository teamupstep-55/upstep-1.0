import { useState } from 'react'
import { api } from '../../api'
import { fmtDate, fmtDateTime } from '../../util'
import { Async, Badge, Empty, Err, PageHead, useAction, useFetch, useToast } from '../../components/ui'

export default function TestResults() {
  const st = useFetch('/staff/test-results')
  const toast = useToast()
  const { busy, error, run } = useAction()

  const shortlist = async (aid) => {
    if (!confirm('Shortlist this student? A congratulations email will be sent.')) return
    const r = await run(() => api(`/staff/applications/${aid}/shortlist`, { method: 'POST' }), 'Student shortlisted! Email sent.')
    if (r) st.reload()
  }

  return (
    <>
      <PageHead title="Test Results" sub="Students who have completed their assessment tests." />
      <Err>{error}</Err>
      <Async state={st}>
        {(d) => !d.results?.length ? (
          <div className="box"><Empty title="No test results yet">Results will appear here once applicants submit their tests.</Empty></div>
        ) : (
          <div className="scroll-x"><table className="tbl">
            <thead><tr><th>Student</th><th>Role</th><th>Score</th><th>Percentage</th><th>Result</th><th>Submitted</th><th>Pipeline</th><th></th></tr></thead>
            <tbody>
              {d.results.map((r) => (
                <tr key={r.submission_id}>
                  <td><b>{r.name}</b><br /><span className="small muted">{r.email}</span></td>
                  <td>{r.role_applied}</td>
                  <td>{r.score} / {r.total_marks}</td>
                  <td>{Number(r.percentage).toFixed(1)}%</td>
                  <td><Badge tone={r.passed ? 'green' : 'red'}>{r.passed ? 'Passed' : 'Failed'}</Badge></td>
                  <td>{fmtDateTime(r.submitted_at)}</td>
                  <td><Badge tone={r.pipeline === 'test_taken' ? 'blue' : r.pipeline === 'shortlisted' ? 'gold' : 'green'}>{r.pipeline?.replace('_', ' ')}</Badge></td>
                  <td>
                    {r.pipeline === 'test_taken' && r.passed && (
                      <button className="btn sm gold" disabled={busy} onClick={() => shortlist(r.application_id)}>Shortlist</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Async>
    </>
  )
}

