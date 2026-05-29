import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Spinner } from "@fluentui/react-components";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * Route guard that redirects unauthenticated users to the landing page.
 */
export function ProtectedRoute({
  children,
}: ProtectedRouteProps): JSX.Element {
  const { isAuthenticated, inProgress } = useAuth();

  if (inProgress) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "4rem" }}>
        <Spinner label="Authenticating..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
