import { Configuration, LogLevel } from "@azure/msal-browser";

/**
 * MSAL configuration for Entra External ID.
 * Environment variables are injected at build time via Vite.
 */
export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_MSAL_CLIENT_ID ?? "",
    authority:
      import.meta.env.VITE_MSAL_AUTHORITY ??
      "https://login.microsoftonline.com/common",
    redirectUri: import.meta.env.VITE_MSAL_REDIRECT_URI ?? "/",
    postLogoutRedirectUri: "/",
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
      loggerCallback: (_level, message) => {
        console.debug("[MSAL]", message);
      },
    },
  },
};

/** Scopes requested when calling the backend API. */
export const apiScopes: string[] = [
  import.meta.env.VITE_API_SCOPE ?? "api://accelerators-api/access_as_user",
];
