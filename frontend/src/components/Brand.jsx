import { Link } from 'react-router-dom'
import { useSite } from '../auth'

export function Brand({ light }) {
  const { company_name } = useSite()
  return (
    <Link to="/" className="brand" aria-label={`${company_name} home`}>
      <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="10" fill={light ? '#ffffff' : '#5468d4'} />
        <path d="M8 22 L14 14 L18 18 L24 9" stroke={light ? '#5468d4' : '#ffffff'} strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="24" cy="9" r="2.4" fill="#f4868c" />
      </svg>
      <span>{company_name}</span>
    </Link>
  )
}
