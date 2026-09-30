import { NavLink } from 'react-router-dom';

const linkBase =
  'text-sm font-medium transition-colors hover:text-white';
const linkClass = ({ isActive }: { isActive: boolean }) =>
  `${linkBase} ${isActive ? 'text-white' : 'text-white/55'}`;

export default function Header() {
  return (
    <header className="bg-navy text-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-5">
        <div className="flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white shadow-sm">
            <img src="/publix.svg" alt="Publix" className="h-7 w-7" />
          </div>
          <div>
            <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-widest text-white/60">
              <span>Publix</span>
              <span className="text-lava">&times;</span>
              <img src="/databricks.svg" alt="Databricks" className="h-3.5" />
            </div>
            <h1 className="text-2xl font-bold leading-tight">Store Pulse</h1>
          </div>
        </div>

        <nav className="flex items-center gap-6">
          <NavLink to="/" end className={linkClass}>
            Overview
          </NavLink>
          <NavLink to="/architecture" className={linkClass}>
            Architecture
          </NavLink>
          <div className="hidden text-right sm:block">
            <div className="text-sm font-semibold text-publix-green">Flagship demo</div>
            <div className="text-xs text-white/50">Lakehouse reads &middot; Lakebase actions &middot; Genie</div>
          </div>
        </nav>
      </div>
      <div className="h-1 w-full bg-gradient-to-r from-publix-green via-publix-green to-lava" />
    </header>
  );
}
