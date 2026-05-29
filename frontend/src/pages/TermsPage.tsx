import { Title1, Title2, Body1 } from "@fluentui/react-components";

/**
 * Terms of Service page.
 */
export function TermsPage(): JSX.Element {
  return (
    <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
      <Title1 as="h1">Terms of Service</Title1>
      <Body1 style={{ display: "block", marginTop: "0.5rem", color: "gray" }}>
        Last updated: {new Date().toISOString().split("T")[0]}
      </Body1>

      <section style={{ marginTop: "2rem" }}>
        <Title2 as="h2">1. Acceptance of Terms</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          By accessing and using the Microsoft Accelerators Finder
          (&quot;Service&quot;), you agree to be bound by these Terms of
          Service. If you do not agree, please do not use the Service.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">2. Description of Service</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          The Service provides AI-powered recommendations for Microsoft Azure
          accelerators, reference architectures, and solution templates. The
          Service includes a public search feature and an authenticated chat
          experience.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">3. User Accounts</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          To access the full chat experience, you must sign in using Microsoft
          Entra External ID. You are responsible for maintaining the
          confidentiality of your account credentials.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">4. Acceptable Use</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          You agree not to misuse the Service, including but not limited to:
          attempting to circumvent rate limits, submitting malicious queries,
          or using the Service for purposes other than finding Azure
          accelerators.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">5. Intellectual Property</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          The accelerator content referenced by this Service is owned by their
          respective authors and is subject to their individual licenses
          (typically MIT or Apache 2.0). The Service itself does not claim
          ownership of any accelerator content.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">6. Limitation of Liability</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          The Service is provided &quot;as is&quot; without warranties of any
          kind. AI-generated recommendations are for informational purposes
          only and should not be the sole basis for architectural decisions.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">7. Changes to Terms</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          We may update these Terms from time to time. Continued use of the
          Service after changes constitutes acceptance of the updated Terms.
        </Body1>
      </section>

      <section style={{ marginTop: "1.5rem" }}>
        <Title2 as="h2">8. Contact</Title2>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          For questions about these Terms, please open an issue on the project
          GitHub repository.
        </Body1>
      </section>
    </main>
  );
}
