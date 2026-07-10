import LegalPage from './LegalPage';

export default function PrivacyPolicyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      field="privacy_policy"
      fallback="This platform has not published a privacy policy yet. Please check back later, or contact your administrator for details on how your data is collected, used, and protected."
    />
  );
}
