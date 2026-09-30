# Export Instructions: PDF & PPTX

## Option 1: Export to PDF (Recommended - Browser)

### macOS / Chrome
1. Open `facilitator-deck.html` in Chrome or Safari
2. Press `Cmd + P` to open Print dialog
3. Set:
   - **Destination**: Save as PDF
   - **Scale**: 100%
   - **Margins**: None
   - **Background graphics**: ✓ Enabled
4. Click **Save** and choose output location (e.g., `facilitator-deck.pdf`)

### Windows / Chrome
1. Open `facilitator-deck.html` in Chrome
2. Press `Ctrl + P` to open Print dialog
3. Set:
   - **Destination**: Save as PDF
   - **Scale**: 100%
   - **Margins**: None
   - **Background graphics**: ✓ Enabled
4. Click **Save**

### Chrome Headless (CLI - High Quality)
```bash
# Install Chrome (if not present)
# macOS:
brew install chromium

# Linux:
sudo apt-get install chromium-browser

# Then run:
google-chrome --headless --disable-gpu --print-to-pdf=facilitator-deck.pdf \
  --print-to-pdf-no-header \
  file:///Users/kabeer.singhthockchom/Projects/publix-workshop-slides/facilitator-deck.html
```

### Tips for PDF Export
- **Slide size**: Optimized for 16:9 (1920×1080)
- **Colors**: Navy, Lava, and Publix green will render accurately
- **Fonts**: DM Sans embedded via system fallbacks; ensure DM Sans is installed locally for best results
- **File size**: ~5-15 MB depending on browser rendering

---

## Option 2: Export to PowerPoint (.pptx)

### Method 1: LibreOffice Impress (via ODP)

1. **Convert HTML to ODP** (Open Document Presentation)
   - Open LibreOffice Impress
   - File → Open
   - Select `facilitator-deck.html`
   - LibreOffice imports as a new presentation

2. **Adjust Layout** (if needed)
   - Slide Size: Slide → Slide Size → 16:9 (or custom 1920×1080)
   - Verify backgrounds and text alignment

3. **Export to PPTX**
   - File → Export As → Export as Microsoft PowerPoint 2007-365 (.pptx)
   - Name: `facilitator-deck.pptx`
   - Click **Export**

### Method 2: Google Slides (Manual - Highest Fidelity)

1. Create a new Google Slides presentation
2. Set slide size: File → Page setup → Widescreen (16:9)
3. Manually recreate slides in Google Slides using:
   - Theme colors: Navy (`#0B2026`), Lava (`#FF3621`), Publix Green (`#4c8c2b`)
   - Font: DM Sans (or Google Sans as fallback)
   - Copy text from `facilitator-deck.html`
4. Download as PPTX: File → Download → Microsoft PowerPoint (.pptx)

### Method 3: Online Converter

- Use a service like **CloudConvert**, **Zamzar**, or **Online-Convert**:
  1. Upload `facilitator-deck.html`
  2. Select format: PPTX
  3. Download the converted file

### Tips for PPTX Export
- **LibreOffice** preserves layouts best but may require manual color/font tweaks
- **Google Slides** offers full control but requires manual recreation
- **Online converters** are fast but may lose complex styling
- Test colors and fonts on Windows/Mac PowerPoint after export

---

## Option 3: Use open-slide Native Export (if available)

The source React file exists in the open-slide workspace:
```
~/Projects/open-slide/slides/publix-agentic-workshop-facilitator/index.tsx
```

If open-slide provides export:
```bash
cd ~/Projects/open-slide
pnpm build
# Then export via CLI or web UI (check open-slide docs)
```

---

## Post-Export Checklist

After exporting to PDF or PPTX:

- [ ] Verify all 15 slides are present
- [ ] Check color accuracy (Navy, Lava, Publix Green)
- [ ] Verify fonts render correctly (or use fallbacks)
- [ ] Test on Windows and macOS (if distributing to others)
- [ ] Ensure links/URLs are clickable (if any embedded)
- [ ] Review speaker notes if adding them post-export

---

## Troubleshooting

### Colors appear wrong
- **Cause**: Browser color management
- **Fix**: Export from Chrome on macOS (best color accuracy) or use LibreOffice with color profiles enabled

### Fonts are missing
- **Cause**: DM Sans not installed locally
- **Fix**: Install from Google Fonts: https://fonts.google.com/specimen/DM+Sans

### Layout is misaligned
- **Cause**: Different slide aspect ratio
- **Fix**: Ensure slide size is 16:9 (1920×1080) before exporting

### PDF file is too large
- **Cause**: Chrome rendering with high compression
- **Fix**: Use `--print-to-pdf` CLI option or adjust compression in Print dialog

---

## Recommended Workflow

1. **For quick sharing**: Export PDF via browser print (5 minutes)
2. **For editing**: Export to PPTX via LibreOffice (15 minutes)
3. **For web**: Keep HTML version or host on local server
4. **For live presentation**: Use HTML in Chrome fullscreen mode (press F11 for fullscreen, Esc to exit)

---

## File Naming Convention

Use consistent naming for exports:
```
publix-agentic-workshop-facilitator-deck_{VERSION}_{DATE}.{FORMAT}

Examples:
- facilitator-deck_v1.0_2026-09-29.pdf
- facilitator-deck_v1.0_2026-09-29.pptx
```

Store in the project directory or shared drive for version control.

---

**Last Updated**: September 29, 2026
