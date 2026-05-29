import { Link } from "react-router-dom";
import { tokens } from "@fluentui/react-components";

/**
 * Site footer with links to Terms and Privacy pages.
 */
export function Footer(): JSX.Element {
  return (
    <footer
      style={{
        display: "flex",
        justifyContent: "center",
        gap: "1.5rem",
        padding: "1rem",
        borderTop: `1px solid ${tokens.colorNeutralStroke1}`,
        fontSize: "0.85rem",
        color: tokens.colorNeutralForeground3,
      }}
    >
      <Link to="/terms">Terms of Service</Link>
      <Link to="/privacy">Privacy Policy</Link>
      <span>© {new Date().getFullYear()} Microsoft Accelerators Finder</span>
    </footer>
  );
}
