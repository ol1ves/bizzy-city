import { Analytics } from "@vercel/analytics/next"
import type { Metadata } from 'next';
import { Plus_Jakarta_Sans } from 'next/font/google';
import MapProvider from '@/components/MapProvider';
import './globals.css';

const jakarta = Plus_Jakarta_Sans({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'BizzyCity — Find the right business for any space',
  description:
    'AI-powered recommendations for what business to open at commercial properties in Manhattan.',
  icons: {
    icon: '/logo.png',
    apple: '/logo.png',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className={`${jakarta.className} h-full`}>
        <MapProvider>{children}</MapProvider>
        <Analytics />
      </body>
    </html>
  );
}
