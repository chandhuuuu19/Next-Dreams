import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Next Dreams — Find your path",
  description: "Explore connected education and career pathways with Next Dreams.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head><link rel="stylesheet" href="/demo/styles.css" /></head>
      <body>{children}</body>
    </html>
  );
}
