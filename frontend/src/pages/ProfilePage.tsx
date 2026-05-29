import { useState, useEffect } from "react";
import {
  Title1,
  Body1,
  Button,
  Card,
  Spinner,
  Dialog,
  DialogTrigger,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  DialogContent,
  tokens,
} from "@fluentui/react-components";
import { useAuth } from "../auth";

interface UserProfile {
  display_name: string;
  email: string;
  created_at: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * Profile page — user info, data export, account deletion.
 */
export function ProfilePage(): JSX.Element {
  const { getAccessToken, logout } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const token = await getAccessToken();
        const res = await fetch(`${API_BASE}/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          setProfile(await res.json());
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [getAccessToken]);

  const handleExport = async (): Promise<void> => {
    setExporting(true);
    try {
      const token = await getAccessToken();
      const res = await fetch(`${API_BASE}/me/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "my-data-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const handleDelete = async (): Promise<void> => {
    setDeleting(true);
    try {
      const token = await getAccessToken();
      const res = await fetch(`${API_BASE}/me`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        await logout();
      }
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
        <Spinner label="Loading profile..." />
      </main>
    );
  }

  return (
    <main style={{ maxWidth: "48rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
      <Title1 as="h1">Your Profile</Title1>

      {profile && (
        <Card style={{ padding: "1.5rem", marginTop: "1.5rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div>
              <strong>Display Name</strong>
              <Body1 style={{ display: "block" }}>{profile.display_name}</Body1>
            </div>
            <div>
              <strong>Email</strong>
              <Body1 style={{ display: "block" }}>{profile.email}</Body1>
            </div>
            <div>
              <strong>Member since</strong>
              <Body1 style={{ display: "block" }}>
                {new Date(profile.created_at).toLocaleDateString()}
              </Body1>
            </div>
          </div>
        </Card>
      )}

      {/* Data export */}
      <div style={{ marginTop: "2rem" }}>
        <Title1 as="h2" style={{ fontSize: "1.25rem" }}>
          Your Data
        </Title1>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          Download a copy of all your data (profile, conversations, preferences).
        </Body1>
        <Button
          style={{ marginTop: "0.75rem" }}
          onClick={handleExport}
          disabled={exporting}
        >
          {exporting ? "Exporting..." : "Export my data"}
        </Button>
      </div>

      {/* Account deletion */}
      <div style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: `1px solid ${tokens.colorNeutralStroke1}` }}>
        <Title1 as="h2" style={{ fontSize: "1.25rem", color: tokens.colorPaletteRedForeground1 }}>
          Danger Zone
        </Title1>
        <Body1 style={{ display: "block", marginTop: "0.5rem" }}>
          Permanently delete your account and all associated data. This cannot
          be undone.
        </Body1>

        <Dialog>
          <DialogTrigger disableButtonEnhancement>
            <Button
              appearance="primary"
              style={{ marginTop: "0.75rem", backgroundColor: tokens.colorPaletteRedBackground3 }}
            >
              Delete my account
            </Button>
          </DialogTrigger>
          <DialogSurface>
            <DialogBody>
              <DialogTitle>Delete Account</DialogTitle>
              <DialogContent>
                Are you sure you want to permanently delete your account? All
                your conversations, preferences, and profile data will be
                removed. This action cannot be undone.
              </DialogContent>
              <DialogActions>
                <DialogTrigger disableButtonEnhancement>
                  <Button appearance="secondary">Cancel</Button>
                </DialogTrigger>
                <Button
                  appearance="primary"
                  onClick={handleDelete}
                  disabled={deleting}
                  style={{ backgroundColor: tokens.colorPaletteRedBackground3 }}
                >
                  {deleting ? "Deleting..." : "Yes, delete everything"}
                </Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>
      </div>
    </main>
  );
}
