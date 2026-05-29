import React, { createContext, useContext, useMemo } from "react";
import {
  MsalProvider,
  useMsal,
  useIsAuthenticated,
} from "@azure/msal-react";
import {
  PublicClientApplication,
  InteractionStatus,
  AccountInfo,
} from "@azure/msal-browser";
import { msalConfig, apiScopes } from "./msalConfig";

/** Singleton MSAL instance. */
export const msalInstance = new PublicClientApplication(msalConfig);

interface AuthContextValue {
  isAuthenticated: boolean;
  inProgress: boolean;
  account: AccountInfo | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => Promise<string>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function AuthContextProvider({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const account = accounts[0] ?? null;

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated,
      inProgress: inProgress !== InteractionStatus.None,
      account,
      login: async () => {
        await instance.loginRedirect({ scopes: apiScopes });
      },
      logout: async () => {
        await instance.logoutRedirect();
      },
      getAccessToken: async () => {
        const response = await instance.acquireTokenSilent({
          scopes: apiScopes,
          account: account ?? undefined,
        });
        return response.accessToken;
      },
    }),
    [instance, isAuthenticated, inProgress, account],
  );

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

/** Hook to access authentication state and actions. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

/** Top-level auth provider wrapping MsalProvider + context. */
export function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthContextProvider>{children}</AuthContextProvider>
    </MsalProvider>
  );
}
