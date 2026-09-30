# Publix Agentic Workshop - Facilitator Deck

Full-day workshop slide deck for "Agentic End-to-End Developer Experience" co-branded with Publix and Databricks.

## Files Included

- **`facilitator-deck.html`** - Standalone HTML presentation (Reveal.js-based)
- **`publix-agentic-workshop-facilitator-source.tsx`** - Source React component (open-slide format)
- **`EXPORT_INSTRUCTIONS.md`** - Step-by-step export guide to PDF and PPTX

## Slide Overview

**15 slides, ~6-7 minutes per module (facilitator-paced):**

1. **Title** - Co-branded cover with Publix + Databricks
2. **Store Pulse** - The flagship demo (art of the possible)
3. **Architecture** - 5-layer decomposition
4. **Use Cases** - The 3 pillars (real-time sales, dynamic pricing, reference data)
5. **Agentic Workflow** - Describe → Generate → Review → Deploy
6-13. **Module Intros** - 1 slide per module (Kickoff through Wrap-Up)
14. **Take-Home** - Public notebooks repo + prompts playbook
15. **Next Steps** - Extend, Scale, Ship

## Design

- **Palette**: Databricks Navy (`#0B2026`), Lava (`#FF3621`), Publix Green (`#4c8c2b`)
- **Typography**: DM Sans (body and display)
- **Layout**: Lean facilitator deck (frame + transition, minimal text)
- **Narrative**: Art of the possible → Decompose architecture → Guide through modules

## Viewing the Deck

### HTML (Browser)
```bash
open facilitator-deck.html
```
Or serve via a local web server:
```bash
python3 -m http.server 8000
# then visit http://localhost:8000/facilitator-deck.html
```

### React Component (open-slide)
The source file is available in the main open-slide workspace:
```
~/Projects/open-slide/slides/publix-agentic-workshop-facilitator/index.tsx
```

Build and preview:
```bash
cd ~/Projects/open-slide
pnpm dev  # starts dev server at http://localhost:5173
# Navigate to the facilitator deck slide set
```

## Exporting to PDF & PPTX

See `EXPORT_INSTRUCTIONS.md` for detailed steps using:
- **PDF**: Browser print to PDF, or Chrome headless CLI
- **PPTX**: LibreOffice Impress, or open-slide export (if available)

## Customization

To modify slides:
1. **HTML**: Edit `facilitator-deck.html` directly
2. **React**: Edit `~/Projects/open-slide/slides/publix-agentic-workshop-facilitator/index.tsx`, then rebuild

Key sections to update:
- Co-branding logos (Eyebrow eyebrow section)
- Color palette (CSS variables at top of HTML, or design system in TSX)
- Module titles and descriptions
- Live demo URL (update Store Pulse slide)

## Notes

- All 15 slides fit within the "16-20 slides" lean facilitator guideline
- Content is intentionally sparse—slides frame the modules, facilitator carries the narrative
- Live code, apps, and notebook demos are referenced, not embedded
- No speaker notes embedded; add as needed for your delivery style

## Workshop Context

- **Full-day event** (8-9 hours with breaks)
- **~50-60 minutes per module** (Modules 1-8)
- **Target audience**: Data engineers, architects, product managers
- **Deliverables**: By end of day, attendees have:
  - Deployed a multi-layer lakehouse
  - Built an agentic app (Genie + Claude)
  - Submitted a PR to production

---

**Created**: September 29, 2026  
**Co-brand**: Publix + Databricks  
**Format**: HTML (Reveal.js) + React (open-slide)
