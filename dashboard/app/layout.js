import "./globals.css";
import Masthead from "../components/Masthead";

export const metadata = {
  title: "SwarmRoute — Fleet Resilience Summary",
  description:
    "Technical summary of the SWARMRoute decentralized fleet optimization simulation.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <Masthead />
          <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
          <footer className="max-w-5xl mx-auto px-6 py-8 mt-8 border-t border-rule text-xs text-muted mono">
            Compiled from results/ in the SWARMRoute repository. Static
            benchmark output — see the live view page for what a connected
            version would add.
          </footer>
        </div>
      </body>
    </html>
  );
}
