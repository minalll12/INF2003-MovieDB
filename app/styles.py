import streamlit as st

GRAIN = (
    "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E"
    "%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E"
    "%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)'/%3E%3C/svg%3E"
)

CSS = """
<style>
:root {
    --ink: #0d0c0a;
    --surface: #16140f;
    --rule: #2e2a23;
    --paper: #efe8d8;
    --muted: #9a917f;
    --gold: #d4af37;
    --rust: #c4532f;
    --font-display: 'DM Serif Display', Georgia, serif;
    --font-body: 'Inter', system-ui, sans-serif;
    --font-mono: 'DM Mono', 'Courier New', monospace;
    --display: var(--font-display);
    --read: var(--font-body);
    --label: var(--font-mono);
    --gutter: 48px;
}

/* ── Font enforcement ──────────────────────────────────────────────────────── */
/* Base: Inter on text elements only — never a bare `*`, which would also
   repaint Streamlit's icon-font glyphs (e.g. the chevron/arrow spans) as
   literal text like "arrow_down" instead of rendering the icon. */
p,
span:not([class*="icon" i]):not([data-testid*="icon" i]):not([class*="material" i]):not([class*="symbol" i]):not([class*="chevron" i]):not([class*="arrow" i]):not([data-testid*="arrow" i]),
div.stMarkdown,
div[data-testid="stText"], label, .stTextInput label, .stSelectbox label,
button[kind="secondary"],
[data-testid="stAppViewContainer"] h1, [data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3 {
    font-family: 'Inter', system-ui, sans-serif !important;
}

/* DM Serif Display on all headings and display elements */
h1, h2, h3, h4, h5, h6,
[data-testid="stHeading"],
[data-testid="stHeading"] *,
[data-testid="stMarkdown"] h1,
[data-testid="stMarkdown"] h2,
[data-testid="stMarkdown"] h3 {
    font-family: 'DM Serif Display', Georgia, serif !important;
}

/* DM Mono only on nav links, filter labels, pill tags, counts, buttons */
button, label, input, select, textarea, option,
[data-testid="stSelectbox"] *,
[data-testid="stMultiSelect"] *,
[data-testid="stSlider"] *,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTab"] button,
[data-baseweb="tab"] *,
[data-baseweb="select"] *,
nav *, .stButton button, .stFormSubmitButton button {
    font-family: 'DM Mono', 'Courier New', monospace !important;
}

/* Poster card titles always DM Serif Display — override mono rule above */
[class*="st-key-card_"] [data-testid="stBaseButton-tertiary"],
[class*="st-key-card_"] [data-testid="stBaseButton-tertiary"] * {
    font-family: 'DM Serif Display', Georgia, serif !important;
}

/* Streamlit resolves most widget type through these theme variables. */
:root, .stApp, [data-testid="stAppViewContainer"] {
    --default-font-family: var(--read);
    --default-heading-font-family: var(--display);
    --default-code-font-family: var(--label);
}

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: var(--ink);
    color: var(--paper);
    font-family: var(--read);
}

.stApp, .stApp p, .stApp li, .stApp div, .stApp span, .stApp label,
.stApp input, .stApp textarea, .stApp button, .stApp select,
[data-baseweb], [data-baseweb] * {
    font-family: var(--read);
}

/* Streamlit's icon spans carry their glyph as a ligature on their text
   content, so they must keep the icon font no matter what. Scoped under
   .stApp and duplicated with case-insensitive attribute matches so this
   always outranks the plain-text font-enforcement rule above, regardless
   of how Streamlit capitalizes its internal data-testid/class names. */
[data-testid="stIconMaterial"], [data-testid="stExpanderIcon"],
span[class*="material-symbols"], span[class*="material-icons"],
.stApp [data-testid*="icon" i], .stApp [data-testid*="Icon" i],
.stApp [class*="icon" i], .stApp [class*="material" i], .stApp [class*="symbol" i] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}

h1, h2, h3, h4, h5, h6, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    font-family: var(--display) !important;
    font-weight: 400;
    letter-spacing: -0.015em;
    color: var(--paper);
}

/* Grain sits above the page but never intercepts clicks. */
.stApp::after {
    content: "";
    position: fixed;
    inset: 0;
    z-index: 9999;
    pointer-events: none;
    opacity: 0.04;
    background-image: url("__GRAIN__");
    mix-blend-mode: overlay;
}

/* The top navigation lives inside the toolbar, so only its actions are hidden. */
[data-testid="stToolbarActions"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
footer,
#MainMenu { display: none !important; }

[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }

[data-testid="stMainBlockContainer"] {
    max-width: 1200px;
    padding: 8px var(--gutter) 0;
}
@media (max-width: 640px) {
    :root { --gutter: 16px; }
}

/* ---------- masthead / top navigation ---------- */

[data-testid="stHeader"] {
    background: var(--ink);
    border-bottom: 1px solid var(--rule);
}
[data-testid="stHeader"] [data-testid="stHeaderActionElements"] { display: none; }

[data-testid="stToolbar"] {
    display: flex;
    justify-content: center;
    width: 100%;
    background: transparent;
}
[data-testid="stTopNav"] {
    background: transparent;
    gap: 0;
    justify-content: center;
}
[data-testid="stTopNav"] a, [data-testid="stTopNav"] button {
    background: transparent !important;
    border-radius: 0;
    border-left: 1px solid var(--rule);
    padding: 4px 18px !important;
}
[data-testid="stTopNav"] > *:first-child a,
[data-testid="stTopNav"] > *:first-child button { border-left: none; }
[data-testid="stTopNav"] a *, [data-testid="stTopNav"] button * {
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 11px !important;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted) !important;
}
[data-testid="stTopNav"] a:hover *, [data-testid="stTopNav"] button:hover * { color: var(--paper) !important; }
[data-testid="stTopNav"] a[aria-current="page"] *,
[data-testid="stTopNav"] [aria-selected="true"] * { color: var(--gold) !important; font-weight: 500; }
[data-testid="stTopNav"] svg { display: none; }

/* Wordmark and account menu are lifted into the header band. */
[class*="st-key-wordmark"] { position: fixed; top: 16px; left: var(--gutter); z-index: 9998; }
[class*="st-key-account"] { position: fixed; top: 11px; right: var(--gutter); z-index: 9998; }
@media (max-width: 900px) {
    [class*="st-key-wordmark"] .wordmark { font-size: 18px; }
    [class*="st-key-wordmark"] { top: 19px; }
}

.wordmark {
    font-family: var(--display);
    font-weight: 400;
    font-size: 26px;
    letter-spacing: -0.02em;
    line-height: 1;
    color: var(--paper);
    white-space: nowrap;
}
.wordmark em { color: var(--gold); font-style: italic; font-weight: 400; }

/* The account popover is deliberately quiet. */
[data-testid="stPopover"] button {
    font-family: var(--label) !important;
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    border: 1px solid var(--rule);
    background: transparent;
}
[data-testid="stPopover"] button:hover { color: var(--gold); border-color: var(--gold); }
[data-testid="stPopoverBody"] {
    background: var(--surface);
    border: 1px solid var(--rule);
    border-radius: 2px;
}

/* ---------- typography primitives ---------- */

.eyebrow {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
}
.eyebrow::before {
    content: "";
    width: 7px;
    height: 7px;
    background: var(--rust);
    flex: none;
}
.eyebrow.plain::before { display: none; }

.label { font-family: var(--label); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); }
.mono { font-family: var(--label); font-size: 12px; letter-spacing: 0.1em; color: var(--muted); }
.read { font-family: var(--read); font-size: 17px; line-height: 1.6; color: var(--paper); }

.page-title { font-family: var(--display); font-weight: 400; font-size: 48px; line-height: 1.1; margin: 16px 0 4px; }
@media (max-width: 640px) { .page-title { font-size: 32px; } }

.page-subtitle { font-family: var(--read); font-size: 13px; color: var(--muted); margin-bottom: 20px; }

.section-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin: 64px 0 0;
}
.section-head .title {
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #9a917f;
    margin-bottom: 12px;
}
.double-rule { border-top: 2px solid var(--gold); margin-top: 12px; margin-bottom: 32px; }
.double-rule::after { content: ""; display: block; border-top: 1px solid var(--rule); margin-top: 4px; }

/* Discover section headers */
.section-gap { height: 48px; }
.section-head-label {
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--muted);
}
/* Zero Streamlit's default flex gap inside section header containers so
   section-gap / label row / double-rule stack without extra spacing.
   margin-top ensures the block clears any preceding text content. */
[class*="st-key-section_hdr_"] {
    gap: 0 !important;
    margin-top: 32px !important;
}
/* Bring the double-rule flush to the label row; global margin-top: 12px is
   correct elsewhere but makes the rule feel detached inside section headers */
[class*="st-key-section_hdr_"] .double-rule {
    margin-top: 4px !important;
}

/* Editorial card metadata — year left, score + heart grouped right */
.meta-year {
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.08em;
    color: var(--muted);
    padding-left: 4px;
    line-height: 1.2;
}
.meta-score {
    font-family: var(--label);
    font-size: 11px;
    color: var(--gold);
    letter-spacing: 0.06em;
    text-align: right;
    padding-right: 4px;
    line-height: 1.2;
}

.footer { margin: 64px 0 24px; }
.footer-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    padding-top: 16px;
}
.footer-row .links { font-family: var(--label); font-size: 11px; letter-spacing: 0.16em; color: var(--muted); }
.footer-row .links span { margin: 0 10px; }
.footer-row .wordmark { font-size: 18px; }

/* ---------- buttons ---------- */

.stButton > button, .stFormSubmitButton > button, [data-testid="stBaseButton-secondary"] {
    font-family: var(--label) !important;
    font-size: 12px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    border-radius: 2px;
    border: 1px solid var(--paper);
    background: transparent;
    color: var(--paper);
    transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    border-color: var(--gold);
    color: var(--gold);
    background: transparent;
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background: var(--gold) !important;
    border: 1px solid var(--gold) !important;
    color: var(--ink) !important;
    font-weight: 500;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: #e2c159 !important;
    border-color: #e2c159 !important;
    color: var(--ink) !important;
}
[data-testid="stBaseButton-tertiary"] {
    border: none !important;
    background: transparent !important;
    color: var(--paper) !important;
    padding: 0 !important;
    min-height: 0 !important;
}
[data-testid="stBaseButton-tertiary"]:hover { color: var(--gold) !important; }

/* ---------- inputs ---------- */

[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-baseweb="base-input"] {
    background-color: var(--surface) !important;
    border-color: var(--rule) !important;
    border-radius: 2px !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 1px var(--gold);
}
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] div {
    font-family: var(--read) !important;
    color: var(--paper) !important;
}
.stTextInput label p, .stTextArea label p, .stSelectbox label p,
.stMultiSelect label p, .stSlider label p, [data-testid="stWidgetLabel"] p {
    font-family: var(--label) !important;
    font-size: 11px !important;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--muted) !important;
}
[data-baseweb="tag"] {
    background-color: transparent !important;
    border: 1px solid var(--gold) !important;
    border-radius: 2px !important;
    color: var(--gold) !important;
    font-family: var(--label) !important;
    font-size: 11px !important;
    text-transform: uppercase;
}
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"],
[data-testid="stThumbValue"] {
    font-family: var(--label) !important;
    font-size: 11px !important;
    color: var(--muted) !important;
}
[data-testid="stTickBar"] > div { background: var(--gold) !important; }

[data-baseweb="tab-list"] { background: transparent; gap: 24px; border-bottom: 1px solid var(--rule); }
[data-baseweb="tab"] { background: transparent; padding-left: 0; padding-right: 0; }
[data-baseweb="tab"] p {
    font-family: var(--label) !important;
    font-size: 11px !important;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--muted) !important;
}
[data-baseweb="tab"][aria-selected="true"] p { color: var(--gold) !important; }
[data-baseweb="tab-highlight"] { background: var(--gold) !important; }
[data-baseweb="tab-border"] { display: none; }

[data-testid="stExpander"] details { background: var(--surface); border: 1px solid var(--rule); border-radius: 2px; }
[data-testid="stExpander"] summary p { font-family: var(--label) !important; font-size: 11px !important; letter-spacing: 0.16em; text-transform: uppercase; }
[data-testid="stDialog"] > div > div { background: var(--surface); border: 1px solid var(--rule); border-radius: 2px; }
[data-testid="stToast"] { background: var(--surface); border: 1px solid var(--rule); border-radius: 2px; font-family: var(--label); font-size: 12px; }
[data-testid="stCaptionContainer"] p { font-family: var(--label) !important; font-size: 11px !important; letter-spacing: 0.1em; color: var(--muted) !important; }
hr, [data-testid="stDivider"] hr { border-color: var(--rule) !important; }

/* ---------- poster cards ---------- */

.poster-frame {
    position: relative;
    aspect-ratio: 2 / 3;
    overflow: hidden;
    border-radius: 4px;
    outline: 1px solid var(--rule);
    outline-offset: -1px;
    background: var(--surface);
    transition: transform 0.2s ease-out, outline-color 0.2s ease-out;
}
.poster-frame .art {
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center;
    transition: transform 0.2s ease-out;
}
.poster-frame .fallback {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 16px;
    text-align: center;
    background: var(--surface);
}
.poster-frame .fallback-icon { font-size: 48px; opacity: 0.3; line-height: 1; }
.poster-frame .fallback .name { font-family: var(--display); font-weight: 400; font-size: 18px; color: var(--paper); }
.poster-frame.no-image { outline: 1px solid var(--rule); }
.poster-frame .fallback .year { font-family: var(--label); font-size: 13px; letter-spacing: 0.12em; color: var(--muted); }
/* Hover handled via .card-poster-wrap and .editorial-poster-wrap wrappers */
[class*="st-key-card_"]:hover .poster-frame .art { transform: scale(1.03); }

/* Poster grid — 24px column gap, 40px row gap */
[data-testid="stHorizontalBlock"]:has([class*="st-key-card_"]) {
    gap: 24px !important;
    row-gap: 40px !important;
}
/* Text area under each poster — slight horizontal padding */
[class*="st-key-card_"] [data-testid="stBaseButton-tertiary"],
[class*="st-key-card_"] .card-meta,
[class*="st-key-card_"] .editorial-blurb {
    padding-left: 4px !important;
    padding-right: 4px !important;
}

/* Card metadata elements */
.card-score {
    font-family: var(--label);
    font-size: 11px;
    color: var(--gold);
    letter-spacing: 0.06em;
    white-space: nowrap;
    text-align: right;
    padding-right: 2px;
    line-height: 1.2;
    margin: 0;
    display: block;
}
/* Strip default spacing from every Streamlit wrapper element inside the right_
   container so the score text has zero surrounding padding/margin. */
[class*="st-key-right_"] [data-testid="stElementContainer"],
[class*="st-key-right_"] [data-testid="stMarkdownContainer"] {
    margin: 0 !important;
    padding: 0px !important;
    line-height: 1 !important;
}
[class*="st-key-right_"] [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
    padding: 0 !important;
    margin-top: 0 !important;
}
.card-year {
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.08em;
    color: var(--muted);
    padding-left: 4px;
    margin: 2px 0 4px;
    line-height: 1.2;
    display: block;
}

/* Right column (score top-aligned with title, heart bottom-aligned with year):
   st-key-right_* IS the stVerticalBlock — use column layout with space-between
   so score sits at the top (row 1) and ♡ at the bottom (row 2). */
[class*="st-key-right_"] {
    width: 100% !important;
    height: 100% !important;
    flex-direction: column !important;
    align-items: flex-end !important;
    justify-content: space-between !important;
    gap: 4px !important;
}
/* Prevent Streamlit's stVerticalBlockBorderWrapper from expanding to 100% and
   breaking the right-align: every direct child must be auto-width. */
[class*="st-key-right_"] > * {
    width: auto !important;
    min-width: 0 !important;
}
/* Always pin the save/heart container to the bottom, even when the score is
   absent — margin-top:auto consumes all remaining space above it. */
[class*="st-key-right_"] > [data-testid="stLayoutWrapper"]:has([class*="st-key-save_"]) {
    margin-top: auto !important;
}

/* Inner title|right columns horizontal block: stretch so both columns share
   the same height — title+year on the left, score+heart on the right. */
[class*="st-key-card_"]:not([class*="st-key-card_editorial_"]) [data-testid="stHorizontalBlock"] {
    gap: 0 !important;
    align-items: stretch !important;
    margin-top: 24px !important;
    margin-bottom: 0 !important;
}
/* Reduce the per-column padding so the title gets maximum horizontal space. */
[class*="st-key-card_"]:not([class*="st-key-card_editorial_"]) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    padding-left: 2px !important;
    padding-right: 2px !important;
}
/* Ensure every wrapper between the column and st-key-right_ stretches to full
   height so space-between on st-key-right_ actually pins score top / heart bottom. */
[class*="st-key-card_"]:not([class*="st-key-card_editorial_"]) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"],
[class*="st-key-card_"]:not([class*="st-key-card_editorial_"]) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] [data-testid="stLayoutWrapper"] {
    height: 100% !important;
}

/* Card containers: no vertical gap between children (poster, title, meta, blurb).
   Editorial cards were previously excluded but never given their own gap:0 rule —
   that omission caused Streamlit's default ~16px gap to push the meta row away
   from the title, breaking the intended year / score+heart alignment. */
[class*="st-key-card_"]:not([class*="st-key-card_editorial_"]),
[class*="st-key-card_editorial_"] {
    gap: 0 !important;
}
[class*="st-key-card_"] [data-testid="stBaseButton-tertiary"] {
    font-family: var(--display) !important;
    font-weight: 400;
    font-size: 16px !important;
    line-height: 1.35;
    text-align: left;
    letter-spacing: 0;
    text-transform: none;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 56px;
    margin-top: 0;
    margin-bottom: 0;
    white-space: normal;
    padding-top: 0 !important;
}

/* See-all link: right-aligned flush with the section rule.
   st-key-see_all_* is the stVerticalBlock. Vertical position is handled by
   vertical_alignment="bottom" on the st.columns call — no height:100% needed. */
[class*="st-key-see_all_"] {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-end !important;
    width: 100% !important;
}
/* Cover both the old stButton wrapper and any plain div child */
[class*="st-key-see_all_"] > div,
[class*="st-key-see_all_"] [data-testid="stButton"] {
    display: flex !important;
    justify-content: flex-end !important;
    width: 100% !important;
}
[class*="st-key-see_all_"] [data-testid="stBaseButton-tertiary"] {
    font-family: var(--label) !important;
    font-size: 11px !important;
    letter-spacing: 0.10em !important;
    text-transform: uppercase !important;
    padding-right: 0 !important;
    margin-left: auto !important;
}
[data-testid="stColumn"]:has([class*="st-key-see_all_"]) {
    padding-right: 0 !important;
}

/* Grid card poster: padding-bottom trick gives guaranteed 2:3 height so the
   title button always renders BELOW the poster, never overlapping it. */
.card-poster-wrap {
    position: relative;
    width: 100%;
    padding-bottom: 150%;
    overflow: hidden;
    border-radius: 4px;
    outline: 1px solid var(--rule);
    outline-offset: -1px;
    margin-top: 12px;
    transition: transform 0.2s ease-out, outline-color 0.2s ease-out;
}
.card-poster-wrap .poster-frame {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    aspect-ratio: auto !important;
    outline: none !important;
    border-radius: 0 !important;
    transform: none !important;
}
[class*="st-key-card_"]:not([class*="st-key-card_editorial_"]):hover .card-poster-wrap {
    transform: translateY(-4px);
    outline-color: var(--gold);
}
[class*="st-key-save_"] [data-testid="stButton"] {
    display: flex;
    justify-content: flex-end;
}
[class*="st-key-save_"] button {
    border: none !important;
    background: transparent !important;
    color: var(--gold) !important;
    font-size: 15px !important;
    padding: 0 !important;
    min-height: 0 !important;
    letter-spacing: 0;
    margin-top: 16.2px;
}
[class*="st-key-save_"] button:hover { color: #e2c159 !important; }
/* Editorial save: left-align so ♡ sits at the LEFT edge of its narrow column,
   directly adjacent to the right-aligned score text — creating a score+heart cluster */
[class*="st-key-save_editorial_"] [data-testid="stButton"] {
    justify-content: flex-start !important;
}

.genre-tag {
    display: inline-block;
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    border: 1px solid var(--rule);
    border-radius: 2px;
    padding: 3px 9px;
}

/* Genre strip scroll arrows (injected via JS into parent DOM) */
.genre-arrow-wrap {
    position: relative;
    padding: 0 36px;
}
.genre-scroll-btn {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(22, 20, 15, 0.9);
    border: 1px solid #3d3a32;
    color: #9a917f;
    font-size: 20px;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    cursor: pointer;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    line-height: 1;
    transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}
.genre-scroll-btn:hover {
    color: #d4af37;
    border-color: #d4af37;
    background: rgba(22, 20, 15, 1);
}
.genre-scroll-left  { left:  4px; }
.genre-scroll-right { right: 4px; }

/* ---------- hero ---------- */

.hero {
    position: relative;
    min-height: 78vh;
    display: flex;
    align-items: flex-end;
    width: 100vw;
    margin-left: calc(50% - 50vw);
    margin-bottom: 32px;
    padding-bottom: 48px;
    overflow: hidden;
}
.hero-inner { position: relative; width: 100%; max-width: 1280px; margin: 0 auto; padding: 0 var(--gutter); }
.hero-bg {
    position: absolute;
    inset: 0;
    background-size: cover;
    background-position: center 20%;
    filter: blur(18px) saturate(0.85);
    transform: scale(1.1);
    animation: fade 0.4s ease-out;
}
.hero-veil {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, var(--ink) 0%, rgba(13, 12, 10, 0.92) 38%, rgba(13, 12, 10, 0.45) 100%),
                linear-gradient(0deg, var(--ink) 2%, transparent 45%);
}
.hero-body { position: relative; max-width: 620px; }
.hero-title {
    font-family: var(--display);
    font-weight: 400;
    font-size: 88px;
    line-height: 0.95;
    letter-spacing: -0.025em;
    margin: 16px 0;
}
@media (max-width: 900px) { .hero-title { font-size: 56px; } .hero { min-height: 70vh; } }
@media (max-width: 640px) { .hero-title { font-size: 40px; } }
.hero-meta { font-family: var(--label); font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); }
.hero-score { font-family: var(--label); font-size: 13px; letter-spacing: 0.12em; color: var(--gold); margin-top: 8px; }
.hero-blurb {
    font-family: var(--read);
    font-size: 18px;
    line-height: 1.6;
    color: var(--paper);
    margin: 16px 0 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* Hero action buttons and the reel selector are widgets layered over the art. */
[class*="st-key-hero_actions"], [class*="st-key-hero_reel"] { position: relative; margin-top: -24px; }
[class*="st-key-hero_reel"] { justify-content: flex-end; }
[class*="st-key-hero_reel"] button {
    border: none !important;
    background: transparent !important;
    font-family: var(--label) !important;
    font-size: 13px !important;
    color: var(--muted) !important;
    padding: 0 6px !important;
    min-height: 0 !important;
}
[class*="st-key-hero_reel"] button:hover { color: var(--paper) !important; }
[class*="st-key-hero_reel"] [data-testid="stBaseButton-primary"] {
    background: transparent !important;
    color: var(--gold) !important;
    font-size: 22px !important;
}

/* ---------- details ---------- */

.backdrop {
    position: relative;
    width: 100vw;
    margin-left: calc(50% - 50vw);
    height: 340px;
    overflow: hidden;
}
.backdrop .art {
    position: absolute;
    inset: -40px;
    background-size: cover;
    background-position: center 25%;
    filter: blur(26px) saturate(0.8);
}
.backdrop .veil {
    position: absolute;
    inset: 0;
    background: linear-gradient(0deg, var(--ink) 4%, rgba(13, 12, 10, 0.55) 60%, rgba(13, 12, 10, 0.75) 100%);
}
.detail-block { position: relative; margin-top: -220px; }
.detail-poster {
    aspect-ratio: 2 / 3;
    background-size: cover;
    background-position: center;
    border-radius: 4px;
    outline: 1px solid var(--rule);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.7);
}
.detail-title { font-family: var(--display); font-weight: 400; font-size: 64px; line-height: 1; margin: 8px 0 16px; }
@media (max-width: 900px) { .detail-title { font-size: 40px; } .detail-block { margin-top: -160px; } }
.detail-rating { display: flex; align-items: baseline; gap: 8px; margin: 16px 0; }
.detail-rating .score { font-family: var(--label); font-size: 40px; color: var(--gold); line-height: 1; }
.detail-rating .of { font-family: var(--label); font-size: 12px; letter-spacing: 0.12em; color: var(--muted); }
.detail-desc { font-family: var(--read); font-size: 18px; line-height: 1.6; max-width: 640px; margin: 16px 0 24px; }
.credit { margin-bottom: 16px; }
.credit .value { font-family: var(--read); font-size: 17px; color: var(--paper); }
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }

/* ---------- reviews ---------- */

.review { padding: 24px 0; border-top: 1px solid var(--rule); }
.review-top { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.review-who { font-family: var(--label); font-size: 12px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--paper); }
.review-who.own { color: var(--gold); }
.stars { font-family: var(--label); font-size: 13px; letter-spacing: 0.1em; white-space: nowrap; }
.stars .rail { position: relative; display: inline-block; color: var(--rule); }
.stars .fill {
    position: absolute;
    top: 0;
    left: 0;
    overflow: hidden;
    color: var(--gold);
    white-space: nowrap;
}
.stars .exact { color: var(--muted); margin-left: 8px; }
.review-text { font-family: var(--read); font-size: 17px; line-height: 1.6; margin: 8px 0; max-width: 680px; }
.review-date { font-family: var(--label); font-size: 11px; letter-spacing: 0.1em; color: var(--muted); }
[class*="st-key-del_"] button { color: var(--rust) !important; }
[class*="st-key-del_"] button:hover { color: #d9673f !important; }

/* ---------- profile ---------- */

.avatar {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    background: var(--surface);
    border: 1px solid var(--gold);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--display);
    font-weight: 400;
    font-size: 34px;
    color: var(--gold);
}
.stat { padding: 0 24px; border-left: 1px solid var(--rule); }
.stat:first-child { border-left: none; padding-left: 0; }
.stat .figure { font-family: var(--display); font-weight: 400; font-size: 52px; line-height: 1.1; color: var(--paper); }
.stat .name { font-family: var(--font-body); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); }

/* ---------- sign in ---------- */

.wall {
    position: fixed;
    inset: 0;
    overflow: hidden;
    background: var(--ink);
    z-index: -1;
    pointer-events: none;
}
.wall-grid {
    position: absolute;
    top: -30%;
    left: -12%;
    width: 124%;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 16px;
    transform: rotate(-8deg);
    animation: drift 90s linear infinite;
}
.wall-grid .art { aspect-ratio: 2 / 3; background-size: cover; background-position: center; border-radius: 4px; background-color: #3d2d1a; }
.wall-veil {
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, rgba(13, 12, 10, 0.72) 0%, rgba(13, 12, 10, 0.97) 78%);
}
[data-testid="stMain"] > div { position: relative; z-index: 1; }

.masthead-plate { text-align: center; padding: 24px 0 40px; }
.masthead-plate .rule { border-top: 1px solid var(--rule); max-width: 560px; margin: 0 auto; }
.masthead-plate .name {
    font-family: var(--display);
    font-weight: 400;
    font-size: 112px;
    line-height: 1;
    letter-spacing: -0.03em;
    padding: 8px 0;
}
.masthead-plate .name em { color: var(--gold); font-style: italic; }
.masthead-plate .vol { font-family: var(--label); font-size: 11px; letter-spacing: 0.3em; color: var(--muted); padding-top: 8px; }
.masthead-plate .tagline { font-family: var(--read); font-style: italic; font-size: 20px; color: rgba(239,232,216,0.8); padding-top: 8px; margin-bottom: 0; }
@media (max-width: 640px) { .masthead-plate .name { font-size: 56px; } .masthead-plate .tagline { font-size: 17px; } }

/* Login input fields get a subtle gold border to feel premium. */
[class*="st-key-auth_panel"] [data-testid="stTextInput"] input {
    border: 1px solid rgba(212, 175, 55, 0.3) !important;
    border-radius: 2px !important;
}
[class*="st-key-auth_panel"] [data-testid="stTextInput"] [data-baseweb="input"]:focus-within input {
    border-color: var(--gold) !important;
}

/* The demo entry stays a quiet text link under the main form. */
[class*="st-key-demo_entry"] [data-testid="stExpander"] details {
    background: transparent;
    border: none;
}
[class*="st-key-demo_entry"] summary { justify-content: center; }
[class*="st-key-demo_entry"] summary p { font-size: 13px !important; color: var(--muted) !important; }
[class*="st-key-demo_entry"] summary svg { display: none; }

[class*="st-key-auth_panel"] {
    background: rgba(22, 20, 15, 0.92);
    border: 1px solid rgba(212, 175, 55, 0.2);
    border-radius: 2px;
    padding: 24px;
}

/* ---------- editorial header (Discover page) ---------- */

.editorial-label {
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--gold);
    margin-top: 24px;
}
.editorial-title {
    font-family: var(--display);
    font-weight: 400;
    font-size: 56px;
    line-height: 1;
    letter-spacing: -0.02em;
    color: var(--paper);
    margin: 12px 0 32px;
}
@media (max-width: 640px) { .editorial-title { font-size: 36px; } }
.editorial-blurb {
    font-family: var(--read) !important;
    font-size: 14px;
    line-height: 1.7;
    color: var(--muted);
    margin: 16px 0 32px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: calc(14px * 1.7 * 3); /* ~72px: equalises card heights when description is absent */
}

/* Editorial metadata row: year + score on the same line */
.editorial-meta-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-left: 4px;
}
.card-year-inline {
    font-family: var(--label);
    font-size: 11px;
    letter-spacing: 0.08em;
    color: var(--muted);
    line-height: 1.2;
}
.card-score-inline {
    font-family: var(--label);
    font-size: 11px;
    color: var(--gold);
    letter-spacing: 0.06em;
    white-space: nowrap;
    line-height: 1.2;
}
/* Editorial cards: equal-width flex row so the 3 cards never overlap or
   collide, regardless of poster size or blurb length. */
[data-testid="stHorizontalBlock"]:has([class*="st-key-card_editorial_"]) {
    display: flex !important;
    flex-wrap: nowrap !important;
    gap: 24px !important;
    overflow: hidden !important;
    width: 100% !important;
}
[data-testid="stHorizontalBlock"]:has([class*="st-key-card_editorial_"]) > [data-testid="stColumn"] {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    max-width: calc(33.33% - 12px) !important;
}
/* Editorial poster: padding-bottom trick guarantees 2:3 height regardless of
   absolutely-positioned children (aspect-ratio alone is unreliable here). */
.editorial-poster-wrap {
    position: relative;
    width: 100%;
    padding-bottom: 150%;
    overflow: hidden;
    border-radius: 4px;
    outline: 1px solid var(--rule);
    outline-offset: -1px;
    transition: transform 0.2s ease-out, outline-color 0.2s ease-out;
}
.editorial-poster-wrap .poster-frame {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    aspect-ratio: auto !important;
    outline: none !important;
    border-radius: 0 !important;
    transform: none !important;
}
[class*="st-key-card_editorial_"]:hover .editorial-poster-wrap {
    transform: translateY(-4px);
    outline-color: var(--gold);
}
[class*="st-key-card_editorial_"] [data-testid="stBaseButton-tertiary"] {
    font-size: 18px !important;
    line-height: 1.3 !important;
    min-height: auto !important;
    margin-top: 24px !important;
    margin-bottom: 0 !important;
    padding-top: 0 !important;
}

/* Editorial meta|save row: no CSS gap, vertically centred */
[class*="st-key-card_editorial_"] [data-testid="stHorizontalBlock"] {
    gap: 0 !important;
    align-items: center !important;
    margin-top: 8px !important;
    margin-bottom: 0 !important;
}
[class*="st-key-card_editorial_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    padding-left: 2px !important;
    padding-right: 2px !important;
}

/* ---------- fresh review cards (No. 03) ---------- */

/* Title button — match grid card (serif, normal case, 2-line clamp) */
[class*="st-key-fresh_"] [data-testid="stBaseButton-tertiary"] {
    font-family: var(--display) !important;
    font-weight: 400;
    font-size: 14px !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    line-height: 1.3;
    text-align: left;
    padding: 0 !important;
    color: var(--paper) !important;
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 38px;
    margin-top: 10px;
    margin-bottom: 4px;
}

/* Username — quiet mono label, muted */
[class*="st-key-fresh_"] .review-who {
    font-size: 10px !important;
    letter-spacing: 0.12em;
    color: var(--muted) !important;
    margin-top: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Star rating row — compact */
[class*="st-key-fresh_"] .stars { font-size: 11px; display: block; margin-top: 2px; }
[class*="st-key-fresh_"] .stars .exact { font-size: 10px; }

/* Poster fallback: hide duplicate title/year in all no-image frames — the
   info is already shown in the label/button below the poster. */
.poster-frame.no-image .fallback .name,
.poster-frame.no-image .fallback .year { display: none; }
.poster-frame.no-image .fallback-icon { font-size: 36px; opacity: 0.18; }

/* ---------- benchmarks ---------- */

[data-testid="stMetricValue"] { font-family: var(--label) !important; color: var(--gold); font-size: 28px; }
[data-testid="stMetricLabel"] p { font-family: var(--label) !important; font-size: 11px !important; letter-spacing: 0.16em; text-transform: uppercase; }
[data-testid="stDataFrame"] { border: 1px solid var(--rule); border-radius: 2px; }
.bench-row { display: grid; grid-template-columns: 2.4fr 1fr 1fr 0.8fr; gap: 16px; padding: 12px 0; border-top: 1px solid var(--rule); align-items: center; }
.bench-row.head { border-top: none; }
.bench-row .q { font-family: var(--read); font-size: 17px; }
.bench-row .n { font-family: var(--label); font-size: 13px; color: var(--paper); text-align: right; }
.bench-row .w { font-family: var(--label); font-size: 12px; letter-spacing: 0.12em; color: var(--gold); text-align: right; }
.bench-row .h { font-family: var(--label); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); }
.bench-row .h.right { text-align: right; }

/* ---------- genre scroll strip (Discover) ---------- */

.genre-scroll-wrap {
    margin-top: 48px;
    margin-bottom: 40px;
    padding-bottom: 4px;
    /* prevent Streamlit markdown wrapper from adding extra padding */
}
.genre-scroll {
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}
.genre-scroll::-webkit-scrollbar { display: none; }
.genre-pill {
    display: inline-block;
    flex-shrink: 0;
    font-family: var(--label) !important;
    font-size: 11px;
    font-weight: 400;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 6px 16px;
    border: 1px solid var(--rule);
    border-radius: 20px;
    background: transparent;
    color: var(--muted);
    cursor: default;
    transition: border-color 0.15s ease, color 0.15s ease;
    white-space: nowrap;
}
.genre-pill:hover {
    border-color: var(--gold);
    color: var(--gold);
}

/* Browse clear button — keep it compact, align vertically with adjacent dropdowns */
[class*="st-key-browse_clear"] {
    margin-top: -8px !important;
    margin-bottom: 8px !important;
}
[class*="st-key-browse_clear"] button {
    font-size: 11px !important;
    letter-spacing: 0.1em !important;
    white-space: nowrap;
}

/* ---------- dark dropdowns / selects ---------- */

[data-baseweb="popover"], [data-baseweb="menu"] {
    background: var(--surface) !important;
    border: 1px solid var(--rule) !important;
}
[data-baseweb="menu"] ul { background: var(--surface) !important; }
[data-baseweb="option"] {
    background: var(--surface) !important;
    color: var(--paper) !important;
    font-family: var(--label) !important;
    font-size: 12px !important;
}
[data-baseweb="option"]:hover { background: var(--rule) !important; }

/* ---------- pagination ---------- */

/* Add breathing room around pagination rows */
[data-testid="stElementContainer"]:has(> [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-tertiary"]):not(:has([class*="st-key-card_"])):not(:has([class*="st-key-genre_strip"])):not(:has([class*="st-key-see_all_"])) {
    margin-top: 16px;
    margin-bottom: 16px;
}

/* ---------- empty states ---------- */

.empty { text-align: center; padding: 96px 24px; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.empty .line { font-family: var(--read); font-style: italic; font-size: 20px; color: var(--muted); max-width: 440px; margin: 0 auto; }

/* ---------- mobile responsive ---------- */

@media (max-width: 768px) {
    /* Poster grids: force 2 columns by wrapping each column to 50% */
    [data-testid="stHorizontalBlock"]:has([class*="st-key-card_"]) {
        flex-wrap: wrap !important;
        gap: 16px !important;
    }
    [data-testid="stHorizontalBlock"]:has([class*="st-key-card_"]) > [data-testid="stColumn"] {
        min-width: calc(50% - 8px) !important;
        flex: 0 0 calc(50% - 8px) !important;
    }
    /* Browse filters: stack vertically */
    [data-testid="stHorizontalBlock"]:has([data-testid="stMultiSelect"]) {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"]:has([data-testid="stMultiSelect"]) > [data-testid="stColumn"] {
        min-width: 100% !important;
        flex: 0 0 100% !important;
    }
}

@media (max-width: 640px) {
    /* Editorial picks: single column */
    [data-testid="stHorizontalBlock"]:has([class*="st-key-card_editorial_"]) {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"]:has([class*="st-key-card_editorial_"]) > [data-testid="stColumn"] {
        min-width: 100% !important;
        flex: 0 0 100% !important;
    }
    /* Stats band: 2×2 grid */
    [data-testid="stHorizontalBlock"]:has(.stat) {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"]:has(.stat) > [data-testid="stColumn"] {
        min-width: calc(50% - 8px) !important;
        flex: 0 0 calc(50% - 8px) !important;
    }
    /* Genre strip is already horizontally scrollable via .genre-scroll */
}

@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes drift { from { transform: rotate(-8deg) translateY(0); } to { transform: rotate(-8deg) translateY(-25%); } }

@media (prefers-reduced-motion: reduce) {
    .wall-grid, .hero-bg { animation: none; }
}
@media (prefers-reduced-motion: no-preference) {
    [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"],
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] { animation: rise 0.5s ease-out both; }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div:nth-child(1) { animation-delay: 0.06s; }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div:nth-child(2) { animation-delay: 0.12s; }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div:nth-child(3) { animation-delay: 0.18s; }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div:nth-child(4) { animation-delay: 0.24s; }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div:nth-child(5) { animation-delay: 0.3s; }
    [data-testid="stMain"] [data-testid="stHorizontalBlock"] > div:nth-child(6) { animation-delay: 0.36s; }
    /* An animated ancestor would become the containing block for the fixed wall. */
    [data-testid="stElementContainer"]:has(.wall) { animation: none; }
}
</style>
"""


FONT_LINKS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1'
    '&family=Inter:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap"'
    ' rel="stylesheet">'
)

# Belt-and-suspenders font overrides, injected as a separate st.markdown call
# after the main CSS, in case a widget's own stylesheet loads after ours and
# would otherwise win the cascade.
FONT_OVERRIDES = """
<style>
[data-testid="stMarkdown"] h1, [data-testid="stMarkdown"] h2, [data-testid="stMarkdown"] h3,
.main h1, .main h2, .main h3, h1, h2, h3 {
    font-family: 'DM Serif Display', Georgia, serif !important;
}
.main p, .main label, .main button, p, label, button {
    font-family: 'Inter', system-ui, sans-serif !important;
}
[class*="mono"], code {
    font-family: 'DM Mono', monospace !important;
}

p,
span:not([class*="icon" i]):not([data-testid*="icon" i]):not([class*="material" i]):not([class*="symbol" i]):not([class*="chevron" i]):not([class*="arrow" i]):not([data-testid*="arrow" i]),
div.stMarkdown,
div[data-testid="stText"], label, .stTextInput label, .stSelectbox label,
button[kind="secondary"] {
    font-family: var(--font-body) !important;
}
h1, h2, h3 { font-family: var(--font-display) !important; font-weight: 400 !important; }
.stApp [data-testid*="icon" i], .stApp [class*="icon" i],
.stApp [class*="material" i], .stApp [class*="symbol" i] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}
</style>
"""


def apply_theme():
    st.markdown(FONT_LINKS, unsafe_allow_html=True)
    st.markdown(CSS.replace("__GRAIN__", GRAIN), unsafe_allow_html=True)
    st.markdown(FONT_OVERRIDES, unsafe_allow_html=True)
