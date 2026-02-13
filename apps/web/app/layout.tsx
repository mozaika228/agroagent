import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AgroAgent",
  description: "AI-agent platform for agriculture"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

