import "@/index.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Landing from "@/pages/Landing";
import AppLayout from "@/components/AppLayout";
import Dashboard from "@/pages/Dashboard";
import KOLWatchlist from "@/pages/KOLWatchlist";
import Trending from "@/pages/Trending";
import TokenDetail from "@/pages/TokenDetail";
import Portfolio from "@/pages/Portfolio";
import SettingsPage from "@/pages/Settings";

function App() {
  return (
    <div className="App font-display bg-[#050505] text-white min-h-screen">
      <BrowserRouter>
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0A0A0D",
              border: "1px solid #1A1A24",
              color: "#fff",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: "12px",
              borderRadius: "2px",
            },
          }}
        />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="kol" element={<KOLWatchlist />} />
            <Route path="trending" element={<Trending />} />
            <Route path="token/:addr" element={<TokenDetail />} />
            <Route path="portfolio" element={<Portfolio />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
