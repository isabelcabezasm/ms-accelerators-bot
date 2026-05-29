import { useState, useRef, useEffect } from "react";
import {
  Title1,
  Button,
  Textarea,
  Card,
  CardHeader,
  Badge,
  Spinner,
  tokens,
} from "@fluentui/react-components";
import {
  ThumbLike20Regular,
  ThumbDislike20Regular,
} from "@fluentui/react-icons";
import { useAuth } from "../auth";

interface Citation {
  title: string;
  url: string;
}

interface AcceleratorCard {
  name: string;
  summary: string;
  tags: string[];
  url: string;
  github_url?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  cards?: AcceleratorCard[];
  citations?: Citation[];
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * Chat page where authenticated users interact with the AI assistant.
 * Renders recommendations as structured accelerator cards.
 */
export function ChatPage(): JSX.Element {
  const { getAccessToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (): Promise<void> => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const token = await getAccessToken();
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
        }),
      });

      if (!res.ok) {
        const errText = res.status === 429
          ? "Daily quota exceeded. Please try again tomorrow."
          : `Error (${res.status})`;
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: errText },
        ]);
        return;
      }

      const data = await res.json();
      setConversationId(data.conversation_id);

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: data.answer ?? "",
        cards: data.accelerators ?? [],
        citations: data.citations ?? [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Network error. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      style={{
        maxWidth: "48rem",
        margin: "0 auto",
        padding: "1.5rem",
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 8rem)",
      }}
    >
      <Title1 as="h1" style={{ marginBottom: "1rem" }}>
        Chat with Accelerator Assistant
      </Title1>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          paddingBottom: "1rem",
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: tokens.colorNeutralForeground3, textAlign: "center", marginTop: "3rem" }}>
            Ask me about Azure accelerators, reference architectures, or
            solution templates!
          </p>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
            }}
          >
            {/* Message bubble */}
            <div
              style={{
                padding: "0.75rem 1rem",
                borderRadius: "12px",
                backgroundColor:
                  msg.role === "user"
                    ? tokens.colorBrandBackground
                    : tokens.colorNeutralBackground3,
                color:
                  msg.role === "user"
                    ? tokens.colorNeutralForegroundOnBrand
                    : tokens.colorNeutralForeground1,
              }}
            >
              {msg.content}
            </div>

            {/* Accelerator cards */}
            {msg.cards && msg.cards.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
                {msg.cards.map((card, ci) => (
                  <Card key={ci} style={{ padding: "0.75rem" }}>
                    <CardHeader
                      header={<strong>{card.name}</strong>}
                      description={card.summary}
                    />
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
                      {card.tags?.map((tag) => (
                        <Badge key={tag} appearance="outline" size="small">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem", fontSize: "0.85rem" }}>
                      {card.url && (
                        <a href={card.url} target="_blank" rel="noopener noreferrer">
                          accelerators.ms
                        </a>
                      )}
                      {card.github_url && (
                        <a href={card.github_url} target="_blank" rel="noopener noreferrer">
                          GitHub
                        </a>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* Citations */}
            {msg.citations && msg.citations.length > 0 && (
              <div style={{ marginTop: "0.5rem", fontSize: "0.8rem" }}>
                <strong>Sources:</strong>{" "}
                {msg.citations.map((c, ci) => (
                  <span key={ci}>
                    <a href={c.url} target="_blank" rel="noopener noreferrer">
                      {c.title}
                    </a>
                    {ci < (msg.citations?.length ?? 0) - 1 && ", "}
                  </span>
                ))}
              </div>
            )}

            {/* Feedback buttons for assistant messages */}
            {msg.role === "assistant" && msg.content && !msg.content.startsWith("Error") && (
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem" }}>
                <Button
                  icon={<ThumbLike20Regular />}
                  size="small"
                  appearance="subtle"
                  aria-label="Helpful"
                />
                <Button
                  icon={<ThumbDislike20Regular />}
                  size="small"
                  appearance="subtle"
                  aria-label="Not helpful"
                />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ alignSelf: "flex-start" }}>
            <Spinner size="small" label="Thinking..." />
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
        <Textarea
          placeholder="Ask about accelerators..."
          value={input}
          onChange={(_, data) => setInput(data.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          style={{ flex: 1 }}
          resize="vertical"
        />
        <Button
          appearance="primary"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
        >
          Send
        </Button>
      </div>
    </main>
  );
}
