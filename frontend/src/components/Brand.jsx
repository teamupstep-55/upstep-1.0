import { Link } from 'react-router-dom'
import { useSite } from '../auth'

export function Brand({ light }) {
  const { company_name } = useSite()
  return (
    <Link to="/" className="brand" aria-label={`${company_name} home`}>
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill={light ? '#f2b01e' : '#12263f'} />
        <path d="M8 22 L14 14 L18 18 L24 9" stroke={light ? '#12263f' : '#f2b01e'} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span>{company_name}</span>
    </Link>
  )
}
