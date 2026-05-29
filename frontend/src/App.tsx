import { BrowserRouter, Routes, Route } from "react-router-dom";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { AuthProvider } from "./auth";
import { Header, Footer, ProtectedRoute } from "./components";
import {
  LandingPage,
  ChatPage,
  HistoryPage,
  ProfilePage,
  TermsPage,
  PrivacyPage,
} from "./pages";

function App(): JSX.Element {
  return (
    <BrowserRouter>
      <FluentProvider theme={webLightTheme}>
        <AuthProvider>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              minHeight: "100vh",
            }}
          >
            <Header />
            <div style={{ flex: 1 }}>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route
                  path="/chat"
                  element={
                    <ProtectedRoute>
                      <ChatPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/history"
                  element={
                    <ProtectedRoute>
                      <HistoryPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute>
                      <ProfilePage />
                    </ProtectedRoute>
                  }
                />
                <Route path="/terms" element={<TermsPage />} />
                <Route path="/privacy" element={<PrivacyPage />} />
              </Routes>
            </div>
            <Footer />
          </div>
        </AuthProvider>
      </FluentProvider>
    </BrowserRouter>
  );
}

export default App;
