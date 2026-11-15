import Calendar from '../../components/Calendar'
import { PageHead } from '../../components/ui'

export default function CalendarPage() {
  return (
    <>
      <PageHead title="Calendar" sub="Classes, daily stand-ups, mock interviews and task deadlines in one place." />
      <Calendar />
    </>
  )
}
