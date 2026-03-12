import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "亲声伴 — 让AI陪伴您的父母",
  description: "老人AI陪伴系统，随时随地给父母打电话，AI用温暖的声音陪伴他们",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
