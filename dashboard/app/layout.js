import "./globals.css";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";

export const metadata = {
  title: "SwarmRoute — Fleet Resilience Console",
  description:
    "Dashboard for the SWARMRoute decentralized fleet optimization simulation.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col md:flex-row">
          <Sidebar />
          <div className="flex-1 min-w-0">
            <Topbar />
            <main className="px-6 py-8 max-w-6xl">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
