# Publix Agentic Workshop - Facilitator Deck Manifest

## Project Overview

**Location**: `~/Projects/publix-workshop-slides/`

Full facilitator deck for the Publix x Databricks "Agentic End-to-End Developer Experience" workshop (September 29, 2026).

---

## Delivered Files

### 1. **README.md** (3.2 KB)
- Overview and quick-start guide
- Slide outline (15 slides)
- Design specifications (colors, typography)
- Viewing instructions (HTML, React, open-slide)

### 2. **facilitator-deck.html** (19 KB)
- Standalone HTML presentation using Reveal.js (v4.5)
- Optimized for 1920×1080 (16:9 aspect ratio)
- Embedded CSS styling with full Publix + Databricks branding
- All 15 slides with navigation
- **Ready to open and use immediately in any browser**
- **Export to PDF**: Print to PDF from browser (Cmd+P / Ctrl+P)

### 3. **publix-agentic-workshop-facilitator-source.tsx** (24 KB)
- React component source for the open-slide framework
- Located in: `~/Projects/open-slide/slides/publix-agentic-workshop-facilitator/index.tsx`
- Full TypeScript with design system tokens
- Reusable for open-slide dev server or CI/CD builds

### 4. **EXPORT_INSTRUCTIONS.md** (4.8 KB)
- Step-by-step guide to export to PDF and PPTX
- Three methods per format:
  - **PDF**: Browser print, Chrome headless CLI, online tools
  - **PPTX**: LibreOffice Impress, Google Slides, online converters
- Troubleshooting section
- Post-export checklist

### 5. **MANIFEST.md** (this file)
- File inventory and project summary

---

## Slide Count & Content

**15 slides** (facilitator-paced, ~40 mins of content + live code):

| # | Slide | Duration | Notes |
|---|-------|----------|-------|
| 1 | Title / Cover | 2 min | Co-branded Publix + Databricks |
| 2 | Store Pulse | 3 min | The flagship demo (live URL included) |
| 3 | Architecture | 5 min | 5-layer stack decomposition |
| 4 | Use Cases | 5 min | Real-time sales, dynamic pricing, reference data |
| 5 | Agentic Workflow | 5 min | Describe → Generate → Review → Deploy |
| 6-13 | Module Intros (8 slides) | 40 min | 1 slide per module (Kickoff through Wrap-Up) |
| 14 | Take-Home | 3 min | Deliverables: notebooks repo + prompts playbook |
| 15 | Next Steps | 2 min | Close: Extend, Scale, Ship |

**Total**: ~15 min of slide content + 50-60 min live demos and hands-on per module = Full 8-hour day

---

## Design System

### Colors
```
Navy:        #0B2026  (Databricks primary)
Lava:        #FF3621  (Databricks accent)
Publix:      #4c8c2b  (Publix brand green)
Text:        #ffffff  (bright white)
Text Soft:   #d4d9df  (muted white)
Surface:     #0f1f27  (dark background)
Surface Hi:  #1a2f37  (lighter background)
Muted:       #7a8a96  (low-contrast)
Success:     #4cc9a3  (accent for positive states)
```

### Typography
- **Display**: DM Sans (700 weight) for titles
- **Body**: DM Sans (400 weight) for paragraphs
- **Mono**: JetBrains Mono for labels and metadata

### Layout
- **Canvas**: 1920 × 1080 (16:9)
- **Gutter**: 120px horizontal, 80-100px vertical
- **Grid systems**: 3-column, 4-column, and 5-column layouts
- **Radius**: 12px consistent border radius

---

## Immediate Use

### View in Browser
```bash
# Open HTML directly
open /Users/kabeer.singhthockchom/Projects/publix-workshop-slides/facilitator-deck.html

# Or serve via Python
cd /Users/kabeer.singhthockchom/Projects/publix-workshop-slides
python3 -m http.server 8000
# Visit: http://localhost:8000/facilitator-deck.html
```

### Export to PDF (Recommended)
1. Open `facilitator-deck.html` in Chrome or Safari
2. Press `Cmd + P` (Mac) or `Ctrl + P` (Windows)
3. Click "Save as PDF"
4. Set margins to None, scale to 100%, enable background graphics
5. Save as `facilitator-deck.pdf`

### Export to PPTX (Optional)
See `EXPORT_INSTRUCTIONS.md` for detailed steps using LibreOffice, Google Slides, or online tools.

---

## Brand Assets

The presentation references:
- Publix logo (static text in slides)
- Databricks logo (static text in slides)
- Store Pulse live demo URL: `publix-store-pulse-<workspace-id>.17.azure.databricksapps.com`

No external image files required—all styling is CSS-based for lightweight delivery.

---

## Customization Points

To adapt the deck for your needs:

### Text Updates
- Store Pulse URL (slide 2)
- Module titles and descriptions (slides 6-13)
- Live demo links
- Contact or follow-up information

### Color Adjustments
- All colors defined as CSS variables in `facilitator-deck.html`
- Easily swap colors by editing:
  ```css
  :root {
    --navy: #0B2026;
    --lava: #FF3621;
    --publix-green: #4c8c2b;
    ...
  }
  ```

### React Component
- Edit `publix-agentic-workshop-facilitator-source.tsx` for component-based customization
- Rebuild with `pnpm build` in `~/Projects/open-slide`

---

## Integration with open-slide

The source component integrates with the open-slide framework:

```bash
# View live in dev server
cd ~/Projects/open-slide
pnpm dev
# Navigate to: http://localhost:5173/s/publix-agentic-workshop-facilitator
```

This allows:
- Hot-reload during editing
- Visual inspector for real-time tweaks
- Integration with Claude Code for iterative design
- Export via open-slide CLI (if supported)

---

## Quality Checklist

- [x] 15 slides (within 16-20 lean facilitator guideline)
- [x] Publix x Databricks co-branding applied
- [x] Colors: Navy, Lava, Publix Green, Success
- [x] Typography: DM Sans + JetBrains Mono
- [x] Aspect ratio: 16:9 (1920×1080)
- [x] Minimal text, visual emphasis (facilitator-paced)
- [x] Narrative: Art of possible → Architecture → Modules
- [x] Module slides (8 slides, one per module)
- [x] Take-homes identified (notebooks repo, prompts playbook)
- [x] Export-ready (HTML + instructions for PDF/PPTX)
- [x] No brand asset images missing (styled text + CSS only)
- [x] Live demo URL included (Store Pulse)

---

## Next Steps

1. **Review**: Open `facilitator-deck.html` in browser and review all 15 slides
2. **Export**: Follow `EXPORT_INSTRUCTIONS.md` to generate PDF or PPTX
3. **Share**: Distribute PDF or PPTX to workshop attendees or team
4. **Deliver**: Use HTML in Chrome fullscreen (F11) for live presentation, or use exported PDF/PPTX in PowerPoint
5. **Iterate**: Edit as needed before the workshop; source files are ready for rapid updates

---

## Support

For questions or customization:
- Edit `facilitator-deck.html` directly for quick CSS/text changes
- Edit `publix-agentic-workshop-facilitator-source.tsx` for React-based updates
- Use `EXPORT_INSTRUCTIONS.md` for formatting issues during export

---

**Project Created**: September 29, 2026  
**Status**: ✓ Complete and Export-Ready  
**Format**: HTML (Reveal.js) + React (open-slide)  
**Deliverables**: 15-slide facilitator deck with co-branding
