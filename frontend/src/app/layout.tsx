import type { Metadata } from 'next';
import MapProvider from '@/components/MapProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'BusiCity — Find the right business for any space',
  description:
    'AI-powered recommendations for what business to open at commercial properties in Manhattan.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="h-full">
        <MapProvider>{children}</MapProvider>
      </body>
    </html>
  );
}
