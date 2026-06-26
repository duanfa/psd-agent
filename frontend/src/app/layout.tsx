import "./globals.css";

export const metadata = {
  title: "BrandOS AI 电商设计平台",
  description: "品牌资产、规则版本、生成工作流与历史任务追溯控制台",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
