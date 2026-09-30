import { Route, Routes } from 'react-router-dom';
import AskGenie from './components/AskGenie';
import ActionPanel from './components/ActionPanel';
import Architecture from './components/Architecture';
import Dashboard from './components/Dashboard';
import Header from './components/Header';
import PriceWatch from './components/PriceWatch';

function Overview() {
  return (
    <>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-navy">Store performance</h2>
        <p className="text-sm text-navy/50">
          Snappy reads served from Lakebase Postgres (synced from the Publix medallion gold layer), with a SQL-warehouse fallback.
        </p>
      </div>
      <Dashboard />

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <PriceWatch />
        <ActionPanel />
      </div>

      <div className="mt-10">
        <AskGenie />
      </div>
    </>
  );
}

export default function App() {
  return (
    <div className="min-h-full">
      <Header />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/architecture" element={<Architecture />} />
        </Routes>

        <footer className="mt-12 border-t border-black/10 pt-6 text-center text-xs text-navy/40">
          Publix &times; Databricks · Store Pulse · Lakehouse reads, Lakebase OLTP writes, Genie Q&amp;A
        </footer>
      </main>
    </div>
  );
}
