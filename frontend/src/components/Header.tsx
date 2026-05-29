import { Link } from "react-router-dom";
import { Button, tokens } from "@fluentui/react-components";
import { useAuth } from "../auth";

/**
 * Application header with navigation and auth controls.
 */
export function Header(): JSX.Element {
  const { isAuthenticated, login, logout, account } = useAuth();

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.75rem 1.5rem",
        borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
        backgroundColor: tokens.colorNeutralBackground1,
      }}
    >
      <Link to="/" style={{ textDecoration: "none", color: "inherit" }}>
        <strong>Accelerator Finder</strong>
      </Link>

      <nav style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
        {isAuthenticated && (
          <>
            <Link to="/chat">Chat</Link>
            <Link to="/history">History</Link>
            <Link to="/profile">Profile</Link>
          </>
        )}
        {isAuthenticated ? (
          <Button size="small" onClick={logout}>
            Sign out ({account?.name ?? account?.username ?? "User"})
          </Button>
        ) : (
          <Button appearance="primary" size="small" onClick={login}>
            Sign in
          </Button>
        )}
      </nav>
    </header>
  );
}
