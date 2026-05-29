import { useState } from "react";
import {
  Title1,
  Body1,
  Button,
  Input,
  Card,
  CardHeader,
  Badge,
  Spinner,
  tokens,
} from "@fluentui/react-components";
import { useAuth } from "../auth";

interface AcceleratorResult {
  name: string;
  summary: string;
  tags: string[];
  url: string;
  github_url?: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * Public landing page with demo search for anonymous users.
 * Calls the rate-limited /search endpoint (10 req/min per IP).
 */
export function LandingPage(): JSX.Element {
  const { login } = useAuth();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AcceleratorResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (): Promise<void> => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      const res = await fetch(`${API_BASE}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), top: 5 }),
      });
      if (!res.ok) {
        if (res.status === 429) {
          setError("Rate limit exceeded. Please wait a moment.");
        } else {
          setError(`Search failed (${res.status})`);
        }
        setResults([]);
        return;
      }
      const data = await res.json();
      setResults(data.results ?? []);
    } catch {
      setError("Network error. Please try again.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "3rem 1.5rem" }}>
      <Title1 as="h1">Find the right Azure Accelerator</Title1>
      <Body1
        style={{ marginTop: "1rem", display: "block", maxWidth: "36rem" }}
      >
        Discover Microsoft Azure accelerators, reference architectures, and
        solution templates to jump-start your cloud projects. Try a search
        below or sign in for the full AI chat experience.
      </Body1>

      {/* Search bar */}
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          marginTop: "2rem",
          maxWidth: "36rem",
        }}
      >
        <Input
          placeholder="e.g. landing zone for regulated industries"
          value={query}
          onChange={(_, data) => setQuery(data.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSearch();
          }}
          style={{ flex: 1 }}
        />
        <Button
          appearance="primary"
          onClick={handleSearch}
          disabled={loading || !query.trim()}
        >
          Search
        </Button>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ marginTop: "1.5rem" }}>
          <Spinner label="Searching accelerators..." size="small" />
        </div>
      )}

      {/* Error */}
      {error && (
        <p style={{ marginTop: "1rem", color: tokens.colorPaletteRedForeground1 }}>
          {error}
        </p>
      )}

      {/* Results */}
      {!loading && results.length > 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            marginTop: "1.5rem",
          }}
        >
          {results.map((r, i) => (
            <Card key={i} style={{ padding: "1rem" }}>
              <CardHeader
                header={<strong>{r.name}</strong>}
                description={r.summary}
              />
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
                {r.tags?.map((tag) => (
                  <Badge key={tag} appearance="outline" size="small">
                    {tag}
                  </Badge>
                ))}
              </div>
              <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem" }}>
                {r.url && (
                  <a href={r.url} target="_blank" rel="noopener noreferrer">
                    View on accelerators.ms
                  </a>
                )}
                {r.github_url && (
                  <a href={r.github_url} target="_blank" rel="noopener noreferrer">
                    GitHub
                  </a>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* No results */}
      {!loading && searched && results.length === 0 && !error && (
        <p style={{ marginTop: "1.5rem", color: tokens.colorNeutralForeground3 }}>
          No accelerators found. Try a different query.
        </p>
      )}

      {/* CTA */}
      <div
        style={{
          marginTop: "3rem",
          padding: "1.5rem",
          backgroundColor: tokens.colorNeutralBackground2,
          borderRadius: "8px",
          textAlign: "center",
        }}
      >
        <Body1 style={{ display: "block", marginBottom: "1rem" }}>
          Want personalized recommendations? Sign in for the full AI chat
          experience with conversation history and detailed comparisons.
        </Body1>
        <Button appearance="primary" size="large" onClick={login}>
          Sign in for full chat experience
        </Button>
      </div>
    </main>
  );
}
