import { useEffect } from "react";
import { useAuth } from "../auth";
import { setTokenProvider, apiClient } from "./client";

/**
 * Hook that wires the MSAL token provider into the API client.
 * Call once near the top of the component tree.
 */
export function useApiClient(): typeof apiClient {
  const { getAccessToken } = useAuth();

  useEffect(() => {
    setTokenProvider(getAccessToken);
  }, [getAccessToken]);

  return apiClient;
}

export { apiClient } from "./client";
