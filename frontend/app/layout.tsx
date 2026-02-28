import type { Metadata } from "next";
import { Source_Sans_3, Geist_Mono, Caveat_Brush } from "next/font/google";
import "./globals.css";

const sourceSans = Source_Sans_3({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const caveatBrush = Caveat_Brush({
  variable: "--font-caveat-brush",
  subsets: ["latin"],
  weight: "400",
});

export const metadata: Metadata = {
  title: "sIsland — digital ecosystem to safely surf in the sea of information",
  description: "digital ecosystem to safely surf in the sea of information",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${sourceSans.variable} ${geistMono.variable} ${caveatBrush.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
