import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "短线精灵",
  description: "短线精灵，加密市场短线机会扫描与模拟观察工具"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
