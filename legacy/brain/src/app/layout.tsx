import './globals.css';
export const metadata = { title: 'Recova', description: 'Anticipatory Agentic Health Engine' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}