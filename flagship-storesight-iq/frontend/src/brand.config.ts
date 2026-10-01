/**
 * Customer identity strings — the text counterpart to brand.ts (colors).
 * generate.py rewrites this file from customer_config.yaml (customer.*).
 * Neutral reference defaults below; never hard-code a customer name in a
 * component — import from here so a re-skin is one place.
 */
export const BRAND_CONFIG = {
  customerName: 'Publix',
  productName: 'StoreSight IQ',
  tagline: 'Store Operations Intelligence',
  // Logo asset paths (served from frontend/public). generate.py copies the
  // customer's supplied files here and updates these paths (any extension).
  logoSrc: '/brand-logo.png',
  markSrc: '/brand-mark.png',
  // Prep-vertical vocabulary — generate.py sets these from domain.yaml (prep.*)
  // so the production-prep surface reflects the customer (no hardcoded product names).
  prepEmoji: '🥖',
  prepNoun: 'prep batch',
  prepNounPlural: 'prep batches',
  prepPageTitle: 'Fresh Production',
  // Whether the configurable 5th "prep/production scheduler" surface ships.
  // generate.py sets this from customer_config.yaml (features.prep_scheduler_enabled).
  // false = hide the Prep Scheduler nav item + route (the 6 generic surfaces remain).
  prepSchedulerEnabled: true,
}
