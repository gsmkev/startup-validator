import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Paraguay Startup Validator",
  description: "Validá tu idea de startup contra datos reales del mercado paraguayo",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  );
}
