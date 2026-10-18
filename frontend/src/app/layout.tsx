import type { Metadata } from "next";
import { JetBrains_Mono, Public_Sans } from "next/font/google";
import { ThemeProvider } from "next-themes";

import "./globals.css";

const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });
const jetbrainsMono = JetBrains_Mono({ variable: "--font-jetbrains-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Multiagent PM", template: "%s · Multiagent PM" },
  description: "Project management with AI agents that classify, size and route tickets.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: next-themes sets the theme class before React loads (no flash).
    <html
      lang="en"
      className={`${publicSans.variable} ${jetbrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="flex min-h-full flex-col">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
