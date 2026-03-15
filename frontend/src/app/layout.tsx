import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ServiceWorkerProvider } from "@/components/pwa/ServiceWorkerProvider";

export const metadata: Metadata = {
  title: "Cleanable",
  description: "Smart cleaning services platform — book, track, and manage cleaning jobs",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Cleanable",
  },
  formatDetection: {
    telephone: false,
  },
  openGraph: {
    type: "website",
    title: "Cleanable",
    description: "Smart cleaning services platform",
    siteName: "Cleanable",
  },
};

export const viewport: Viewport = {
  themeColor: "#01696F",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-192x192.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
      </head>
      <body className="min-h-screen bg-surface font-sans antialiased">
        <ServiceWorkerProvider />
        {children}
      </body>
    </html>
  );
}
