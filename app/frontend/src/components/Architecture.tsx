import { useEffect, useRef } from 'react';

/**
 * Live animated architecture diagram of the Publix workshop stack.
 *
 * Zerobus publisher -> Bronze -> SDP pipeline -> Silver -> Gold ->
 *   { Metric View, Genie Agent, Lakebase } -> Store Pulse app
 *
 * Rendered as a single responsive SVG. A pulsing dot travels left->right
 * along each connector path via requestAnimationFrame + getPointAtLength,
 * animating transform/opacity only. Respects prefers-reduced-motion.
 */

const W = 150;
const H = 60;

type NodeSpec = {
  id: string;
  x: number;
  y: number;
  title: string;
  caption: string;
  variant?: 'app';
};

const NODES: NodeSpec[] = [
  { id: 'zerobus', x: 16, y: 240, title: 'Zerobus publisher', caption: 'serverless push, no Kafka' },
  { id: 'bronze', x: 188, y: 240, title: 'Bronze (Delta)', caption: 'raw landing' },
  { id: 'sdp', x: 360, y: 240, title: 'SDP pipeline', caption: 'quality expectations' },
  { id: 'silver', x: 532, y: 240, title: 'Silver', caption: 'cleaned & conformed' },
  { id: 'gold', x: 704, y: 240, title: 'Gold', caption: 'daily rollup' },
  { id: 'metric', x: 934, y: 100, title: 'Metric View', caption: 'governed KPIs' },
  { id: 'genie', x: 934, y: 240, title: 'Genie Agent', caption: 'ask in English' },
  { id: 'lakebase', x: 934, y: 380, title: 'Lakebase', caption: 'sub-second reads' },
  { id: 'app', x: 1164, y: 240, title: 'Store Pulse app', caption: 'live store view', variant: 'app' },
];

const CONNECTORS: { id: string; d: string }[] = [
  { id: 'c1', d: 'M166 270 L188 270' },
  { id: 'c2', d: 'M338 270 L360 270' },
  { id: 'c3', d: 'M510 270 L532 270' },
  { id: 'c4', d: 'M682 270 L704 270' },
  { id: 'c5', d: 'M854 270 C894 270 894 130 934 130' },
  { id: 'c6', d: 'M854 270 L934 270' },
  { id: 'c7', d: 'M854 270 C894 270 894 410 934 410' },
  { id: 'c8', d: 'M1084 130 C1124 130 1124 270 1164 270' },
  { id: 'c9', d: 'M1084 270 L1164 270' },
  { id: 'c10', d: 'M1084 410 C1124 410 1124 270 1164 270' },
];

const NAVY = '#0B2026';
const GREEN = '#4c8c2b';
const LAVA = '#FF3621';

export default function Architecture() {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;

    const paths = Array.from(svg.querySelectorAll<SVGPathElement>('path.flow'));
    const dots = Array.from(svg.querySelectorAll<SVGGElement>('g.flow-dot'));
    if (paths.length === 0) return;

    const lengths = paths.map((p) => p.getTotalLength());
    const placeDot = (i: number, t: number) => {
      const pt = paths[i].getPointAtLength(t * lengths[i]);
      dots[i].setAttribute('transform', `translate(${pt.x} ${pt.y})`);
    };

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      // Static, non-animated: rest each pulse mid-path at reduced emphasis.
      dots.forEach((g, i) => {
        placeDot(i, 0.5);
        g.style.opacity = '0.55';
      });
      return;
    }

    const speed = 130; // px per second, uniform across path lengths
    const progress = paths.map((_, i) => (i * 0.13) % 1);
    let raf = 0;
    let last = performance.now();

    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      for (let i = 0; i < paths.length; i += 1) {
        let t = progress[i] + (speed * dt) / lengths[i];
        if (t > 1) t -= 1;
        progress[i] = t;
        placeDot(i, t);
        const edge = 0.14;
        const fade = t < edge ? t / edge : t > 1 - edge ? (1 - t) / edge : 1;
        dots[i].style.opacity = String(0.9 * fade);
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-navy">Workshop architecture</h2>
          <p className="max-w-2xl text-sm text-navy/55">
            How a store event travels the lakehouse - from a serverless Zerobus push through the medallion
            layers to governed metrics, a Genie agent, and sub-second Lakebase reads behind this app.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-widest text-navy/50">
          <span>Built on</span>
          <img src="/databricks.svg" alt="Databricks" className="h-3.5" />
        </div>
      </div>

      <section className="rounded-2xl border border-black/5 bg-white p-4 shadow-sm sm:p-6">
        <div className="overflow-x-auto">
          <svg
            ref={svgRef}
            viewBox="0 0 1360 500"
            className="h-auto w-full min-w-[760px]"
            style={{ fontFamily: '"DM Sans", system-ui, sans-serif' }}
            role="img"
            aria-label="Data flow: Zerobus publisher to Bronze to SDP pipeline to Silver to Gold, fanning out to Metric View, Genie Agent, and Lakebase, then into the Store Pulse app."
          >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0 0 L10 5 L0 10 z" fill={NAVY} opacity="0.35" />
              </marker>
            </defs>

            {/* Serving-layer zone behind the three branch nodes */}
            <rect x="908" y="82" width="204" height="376" rx="18" fill={GREEN} fillOpacity="0.05" />
            <text
              x="1010"
              y="104"
              textAnchor="middle"
              fontSize="10"
              letterSpacing="1.5"
              fill={GREEN}
              fillOpacity="0.75"
              fontWeight="600"
            >
              SERVING LAYER
            </text>

            {/* Connector paths */}
            <g fill="none" stroke={NAVY} strokeOpacity="0.28" strokeWidth="1.6">
              {CONNECTORS.map((c) => (
                <path key={c.id} className="flow" d={c.d} markerEnd="url(#arrow)" />
              ))}
            </g>

            {/* Traveling pulse dots (one per connector, same order) */}
            <g>
              {CONNECTORS.map((c) => (
                <g key={c.id} className="flow-dot">
                  <circle r="8.5" fill={LAVA} opacity="0.22" />
                  <circle r="4.5" fill={LAVA} />
                </g>
              ))}
            </g>

            {/* Nodes */}
            {NODES.map((n) => {
              const cx = n.x + W / 2;
              const cy = n.y + H / 2;
              const isApp = n.variant === 'app';
              return (
                <g key={n.id}>
                  <rect
                    x={n.x}
                    y={n.y}
                    width={W}
                    height={H}
                    rx="12"
                    fill={isApp ? NAVY : '#ffffff'}
                    stroke={isApp ? NAVY : NAVY}
                    strokeOpacity={isApp ? 1 : 0.12}
                    strokeWidth="1.4"
                  />
                  {!isApp && <circle cx={n.x + 14} cy={n.y + 15} r="3.5" fill={GREEN} />}
                  <text
                    x={cx}
                    y={cy + 5}
                    textAnchor="middle"
                    fontSize="14.5"
                    fontWeight="600"
                    fill={isApp ? '#ffffff' : NAVY}
                  >
                    {n.title}
                  </text>
                  <text
                    x={cx}
                    y={n.y + H + 18}
                    textAnchor="middle"
                    fontSize="11"
                    fill={NAVY}
                    fillOpacity="0.55"
                  >
                    {n.caption}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-black/5 pt-4 text-xs text-navy/50">
          <span className="inline-flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-lava" />
            Pulses show data flowing left to right
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-publix-green" />
            Serving layer powers this app
          </span>
          <span>Motion pauses when your system prefers reduced motion.</span>
        </div>
      </section>
    </div>
  );
}
