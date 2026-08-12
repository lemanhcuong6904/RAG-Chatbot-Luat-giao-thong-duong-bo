import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Luật Giao Thông AI",
  description: "Hệ thống hỏi đáp luật giao thông đường bộ Việt Nam.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
