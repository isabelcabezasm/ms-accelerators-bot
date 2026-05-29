import { Title1, Title2, Body1 } from "@fluentui/react-components";

/**
 * Privacy Policy page — GDPR-compliant disclosure.
 */
export function PrivacyPage(): JSX.Element {
  return (
    <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
      <Title1 as="h1">Privacy Policy</Title1>
      <Body1 style={{ display: "block", marginTop: "0.5rem", color: "gray" }}>
        Last updated: {new Date().toISOString().split("T")[0]}
      </Body1>

      <section style={{ marginTop: "2rem" }}>
        <Title2 as="h2">1. Data We Collect</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          When you sign in, we collect:
        </Body1>
        <ul style={{ marginTop: "0.5rem", paddingLeft: "1.5rem" }}>
          <li>Display name and email address (from Entra External ID)</li>
          <li>Chat conversation history (messages you send and responses)</li>
          <li>Search queries (anonymous users: IP-based rate limiting only)</li>
          <li>Usage telemetry (hashed user identifiers, request counts)</li>
        </ul>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">2. How We Use Your Data</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          Your data is used to:
        </Body1>
        <ul style={{ marginTop: "0.5rem", paddingLeft: "1.5rem" }}>
          <li>Provide personalized accelerator recommendations</li>
          <li>Maintain your conversation history</li>
          <li>Enforce per-user daily quotas</li>
          <li>Improve the quality of the service (aggregated analytics)</li>
        </ul>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">3. Data Storage &amp; Retention</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          Data is stored in Azure Cosmos DB within the West Europe region.
          Conversation history is retained for 90 days unless you delete your
          account. Telemetry data uses SHA-256 hashed identifiers and cannot
          be linked back to you.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">4. Your Rights (GDPR)</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          Under GDPR, you have the right to:
        </Body1>
        <ul style={{ marginTop: "0.5rem", paddingLeft: "1.5rem" }}>
          <li>
            <strong>Access:</strong> View your profile and conversation
            history via the Profile page.
          </li>
          <li>
            <strong>Export:</strong> Download all your data as JSON via the
            &quot;Export my data&quot; button on the Profile page.
          </li>
          <li>
            <strong>Delete:</strong> Permanently delete your account and all
            associated data via the &quot;Delete my account&quot; button.
          </li>
          <li>
            <strong>Rectification:</strong> Update your display name and email
            via your Entra External ID account settings.
          </li>
        </ul>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">5. Third-Party Services</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          The Service uses:
        </Body1>
        <ul style={{ marginTop: "0.5rem", paddingLeft: "1.5rem" }}>
          <li>Microsoft Entra External ID (authentication)</li>
          <li>Azure OpenAI Service (AI recommendations)</li>
          <li>Azure AI Search (accelerator search index)</li>
          <li>Azure Application Insights (anonymized telemetry)</li>
        </ul>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">6. Cookies</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          The Service uses session storage for authentication tokens. No
          third-party tracking cookies are used.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">7. Contact</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          For privacy-related questions or to exercise your data rights,
          please open an issue on the project GitHub repository or contact the
          project maintainer.
        </Body1>
      </section>
    </main>
  );
}
