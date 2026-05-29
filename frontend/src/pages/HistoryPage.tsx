import { useState, useEffect, useCallback } from "react";
import {
  Title1,
  Body1,
  Button,
  Card,
  Spinner,
  tokens,
} from "@fluentui/react-components";
import { useAuth } from "../auth";

interface Conversation {
  id: string;
  preview: string;
  created_at: string;
  message_count: number;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * History page — paginated list of past conversations.
 */
export function HistoryPage(): JSX.Element {
  const { getAccessToken } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const fetchHistory = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const token = await getAccessToken();
      const res = await fetch(`${API_BASE}/me/history?page=${p}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      setConversations(data.conversations ?? []);
      setHasMore((data.conversations ?? []).length >= 10);
    } finally {
      setLoading(false);
    }
  }, [getAccessToken]);

  useEffect(() => {
    fetchHistory(page);
  }, [page, fetchHistory]);

  return (
    <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
      <Title1 as="h1">Conversation History</Title1>

      {loading ? (
        <Spinner label="Loading history..." style={{ marginTop: "2rem" }} />
      ) : conversations.length === 0 ? (
        <Body1
          style={{
            display: "block",
            marginTop: "2rem",
            color: tokens.colorNeutralForeground3,
          }}
        >
          No conversations yet. Start chatting to see your history here.
        </Body1>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1.5rem" }}>
          {conversations.map((c) => (
            <Card key={c.id} style={{ padding: "1rem", cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong>{c.preview}</strong>
                  <div style={{ fontSize: "0.8rem", color: tokens.colorNeutralForeground3 }}>
                    {new Date(c.created_at).toLocaleDateString()} · {c.message_count} messages
                  </div>
                </div>
              </div>
            </Card>
          ))}

          {/* Pagination */}
          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center", marginTop: "1rem" }}>
            <Button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              size="small"
            >
              Previous
            </Button>
            <span style={{ alignSelf: "center" }}>Page {page}</span>
            <Button
              disabled={!hasMore}
              onClick={() => setPage((p) => p + 1)}
              size="small"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </main>
  );
}
