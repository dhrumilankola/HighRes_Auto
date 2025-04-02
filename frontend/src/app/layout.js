import './globals.css';
import { Inter } from 'next/font/google';

// Use Inter font instead of Geist
const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata = {
  title: 'HIGHRES - Job Application Automation',
  description: 'Automate your job applications with HIGHRES',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans`}>
        {children}
      </body>
    </html>
  );
}