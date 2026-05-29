import {
  Button,
  FluentProvider,
  Title1,
  webLightTheme,
} from "@fluentui/react-components";

function App(): JSX.Element {
  return (
    <FluentProvider theme={webLightTheme}>
      <main
        style={{
          display: "grid",
          gap: "1rem",
          margin: "0 auto",
          maxWidth: "48rem",
          padding: "3rem 1.5rem",
        }}
      >
        <Title1>Microsoft Accelerators Finder</Title1>
        <p>
          React, Vite, Fluent UI, and MSAL.js are wired for the public site
          scaffold.
        </p>
        <Button appearance="primary">Start exploring</Button>
      </main>
    </FluentProvider>
  );
}

export default App;
