import { Title1, Body1, Button } from "@fluentui/react-components";
import { useAuth } from "../auth";

/**
 * Public landing page with demo search for anonymous users.
 */
export function LandingPage(): JSX.Element {
  const { login } = useAuth();

  return (
    <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "3rem 1.5rem" }}>
      <Title1 as="h1">Find the right Azure Accelerator</Title1>
      <Body1 style={{ marginTop: "1rem", display: "block" }}>
        Discover Microsoft Azure accelerators, reference architectures, and
        solution templates to jump-start your cloud projects.
      </Body1>

      <div style={{ marginTop: "2rem" }}>
        <p style={{ color: "gray" }}>
          🔍 Demo search coming soon — try the full chat experience by signing
          in.
        </p>
      </div>

      <Button
        appearance="primary"
        size="large"
        style={{ marginTop: "2rem" }}
        onClick={login}
      >
        Sign in for full chat experience
      </Button>
    </main>
  );
}
