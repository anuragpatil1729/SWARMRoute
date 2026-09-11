import "./globals.css";
import "leaflet/dist/leaflet.css";
import Masthead from "../components/Masthead";
import AuthGate from "../components/AuthGate";
import { AuthProvider } from "../lib/AuthContext";

export const metadata = {
  title: "SwarmRoute — Autonomous Fleet Operations",
  description: "Autonomous AI fleet operations, real-time routing, and decentralized mesh resilience platform.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-white text-slate-900 antialiased min-h-screen">
        <AuthProvider>
          <div className="min-h-screen flex flex-col">
            <Masthead />
            <main className="w-full flex-1 px-4 sm:px-6 lg:px-10 py-6">
              <AuthGate>
                {children}
              </AuthGate>
            </main>
            <footer className="w-full border-t border-slate-200 py-5 mt-10 text-xs text-slate-400 font-mono text-center">
              SWARMRoute Autonomous Fleet Operations & Dynamic Mesh Resilience • Powered by Supabase
            </footer>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
