import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cleanable",
  description: "Smart cleaning services platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-surface font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
