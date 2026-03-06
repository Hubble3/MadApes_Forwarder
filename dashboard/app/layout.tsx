import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'MadApes Signal Intelligence',
  description: 'Crypto signal intelligence dashboard',
};

const navItems = [
  { href: '/', label: 'Dashboard' },
  { href: '/signals', label: 'Signals' },
  { href: '/callers', label: 'Callers' },
  { href: '/portfolio', label: 'Portfolio' },
  { href: '/runners', label: 'Runners' },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Providers>
          <nav className="bg-[#1e293b] border-b border-[#334155] px-6 py-3">
            <div className="max-w-7xl mx-auto flex items-center justify-between">
              <span className="text-lg font-bold text-white">MadApes Intelligence</span>
              <div className="flex gap-6">
                {navItems.map((item) => (
                  <a
                    key={item.href}
                    href={item.href}
                    className="text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    {item.label}
                  </a>
                ))}
              </div>
            </div>
          </nav>
          <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
