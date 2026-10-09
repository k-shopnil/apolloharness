import type { Metadata } from "next";
import { Baumans, Onest, Red_Hat_Display } from "next/font/google";
import "./globals.css";
import SiteHeader from "@/components/site-header";
import Comms from "@/components/comms";
import SiteFooter from "@/components/site-footer";

const baumans = Baumans({
  variable: "--font-baumans",
  weight: "400",
  subsets: ["latin"],
});

const onest = Onest({
  variable: "--font-onest",
  weight: ["400", "600", "700", "800"],
  subsets: ["latin"],
});

const redHat = Red_Hat_Display({
  variable: "--font-red-hat",
  weight: "400",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Chhayanautical",
  description: "Team Chhayanautical — Dhaka, Bangladesh.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${baumans.variable} ${onest.variable} ${redHat.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-black text-white">
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <Comms />
        <SiteFooter />
      </body>
    </html>
  );
}
