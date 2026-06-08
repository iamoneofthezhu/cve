import './globals.css';

export const metadata = {
  title: 'CVE Search',
  description: 'Search CVE vulnerabilities using natural language',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
