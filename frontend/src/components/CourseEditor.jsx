/** Editable list of courses with fee ranges (used by the public form, the owner page and the admin screen). */
export const blankCourse = () => ({ title: '', duration: '', fee_min: '', fee_max: '', batch_timing: '' })

export default function CourseEditor({ courses, onChange }) {
  const set = (i, k, v) => onChange(courses.map((c, j) => (j === i ? { ...c, [k]: v } : c)))
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {courses.map((c, i) => (
        <div className="repeat" key={i}>
          <input className="input" placeholder="Course name, e.g. Python for beginners" aria-label={`Course ${i + 1} name`} value={c.title} onChange={(e) => set(i, 'title', e.target.value)} maxLength={160} />
          <div className="g">
            <input className="input" placeholder="Duration" aria-label="Duration" value={c.duration || ''} onChange={(e) => set(i, 'duration', e.target.value)} maxLength={60} />
            <input className="input" placeholder="Fee from (₹)" aria-label="Minimum fee" inputMode="numeric" value={c.fee_min ?? ''} onChange={(e) => set(i, 'fee_min', e.target.value)} />
            <input className="input" placeholder="Fee to (₹)" aria-label="Maximum fee" inputMode="numeric" value={c.fee_max ?? ''} onChange={(e) => set(i, 'fee_max', e.target.value)} />
            <input className="input" placeholder="Batch timing" aria-label="Batch timing" value={c.batch_timing || ''} onChange={(e) => set(i, 'batch_timing', e.target.value)} maxLength={120} />
          </div>
          <div><button type="button" className="btn ghost sm" onClick={() => onChange(courses.filter((_, j) => j !== i))}>Remove course</button></div>
        </div>
      ))}
      <div><button type="button" className="btn ghost sm" onClick={() => onChange([...courses, blankCourse()])}>+ Add a course</button></div>
    </div>
  )
}
