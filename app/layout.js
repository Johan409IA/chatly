import "../assets/auth.css";
import "../assets/chat.css";
import "./globals.css";

export const metadata = {
  title: "Chatly",
  description: "Conversaciones privadas y grupales en español.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
