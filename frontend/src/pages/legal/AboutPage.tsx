import LegalPage from './LegalPage';

export default function AboutPage() {
  return (
    <LegalPage
      title="About"
      field="about_me"
      fallback="This platform helps teachers and administrators manage students, classrooms, exams, and performance analytics. Ask your administrator for more details about this deployment."
    />
  );
}
