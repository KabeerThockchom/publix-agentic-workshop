import AskGenie from './components/AskGenie';
import ActionPanel from './components/ActionPanel';
import Dashboard from './components/Dashboard';
import Header from './components/Header';
import PriceWatch from './components/PriceWatch';

export default function App() {
  return (
    <div className="min-h-full">
      <Header />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-navy">Store performance</h2>
          <p className="text-sm text-navy/50">
            Live reads from the Publix medallion gold layer via the Databricks SQL warehouse.
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

        <footer className="mt-12 border-t border-black/10 pt-6 text-center text-xs text-navy/40">
          Publix &times; Databricks · Store Pulse · Lakehouse reads, Lakebase OLTP writes, Genie Q&amp;A
        </footer>
      </main>
    </div>
  );
}
