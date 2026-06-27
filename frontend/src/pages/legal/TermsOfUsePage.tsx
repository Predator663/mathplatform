import LegalPage from './LegalPage';

export default function TermsOfUsePage() {
  return (
    <LegalPage
      title="Terms of Use"
      field="terms_of_use"
      fallback="This platform has not published its terms of use yet. Please check back later, or contact your administrator for more information."
    />
  );
}
