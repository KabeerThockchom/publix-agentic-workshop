import { ReactNode } from 'react';

export function Card({
  title,
  subtitle,
  children,
  accent,
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  accent?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-black/5 bg-white shadow-sm">
      {(title || subtitle) && (
        <div className="flex items-center justify-between border-b border-black/5 px-5 py-4">
          <div>
            {title && <h2 className="text-base font-semibold text-navy">{title}</h2>}
            {subtitle && <p className="text-xs text-navy/50">{subtitle}</p>}
          </div>
          {accent && <span className="h-2 w-2 rounded-full bg-publix-green" />}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}
