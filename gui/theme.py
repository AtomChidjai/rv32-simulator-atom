"""Dark/light color tokens and global desktop UI styles."""

from nicegui import ui

# ── Concrete hex for the xterm canvas (cannot use CSS vars) ────────────
XTERM_DARK = {"background": "#16161E", "foreground": "#E6E6E0", "cursor": "#818CF8"}
XTERM_LIGHT = {"background": "#F6F7F9", "foreground": "#20232A", "cursor": "#5145E5"}

# ── CSS-variable references (theme-aware, used in inline styles) ───────
# These names are kept stable so other modules import them unchanged.
C_BG        = "var(--bg)"
C_BG_DARK   = "var(--panel)"     # elevated/header surface (name kept for ref-safety)
C_BG_PANEL  = "var(--panel)"
C_FG        = "var(--fg)"
C_FG_DIM    = "var(--fg-dim)"
C_ACCENT    = "var(--accent)"
C_GREEN     = "var(--green)"
C_RED       = "var(--red)"
C_YELLOW    = "var(--yellow)"
C_CYAN      = "var(--cyan)"
C_BORDER    = "var(--border)"
C_CURRENT   = "var(--current)"

# Low-alpha fills for badges / bit-span highlights (one per semantic color).
C_GREEN_SOFT  = "var(--green-soft)"
C_RED_SOFT    = "var(--red-soft)"
C_YELLOW_SOFT = "var(--yellow-soft)"
C_CYAN_SOFT   = "var(--cyan-soft)"
C_ACCENT_SOFT = "var(--accent-soft)"

# CodeMirror theme name per mode (the editor switches via set_theme()).
CM_DARK = "oneDark"
CM_LIGHT = "basicLight"


def inject_global_css():
    """Inject both theme palettes (as CSS vars) + element overrides + no-flash boot."""
    ui.add_head_html('''
    <script>
    // Restore saved theme before first paint to avoid a flash, and align Quasar's
    // dark mode (for select/input popup dropdowns) with it.
    (function () {
        try {
            var t = localStorage.getItem('rv32i_theme') || 'dark';
        } catch (e) { t = 'dark'; }
        document.documentElement.setAttribute('data-theme', t);
        document.documentElement.classList.toggle('q-dark', t === 'dark');
    })();
    </script>
    <style>
        /* ── Palettes: dark is the default (:root with no attribute = dark) ── */
        :root, :root[data-theme="dark"] {
            --bg:           #16161E;
            --panel:        #1E1E28;
            --fg:           #E6E6E0;
            --fg-dim:       #A2A2AC;
            --accent:       #818CF8;
            --green:        #7DD3A0;
            --red:          #F08A9C;
            --yellow:       #E8C87A;
            --cyan:         #7DC8F0;
            --border:       #353542;
            --current:      #2A2D45;
            --context-surface: #252637;
            --context-edge: rgba(255,255,255,0.07);
            --context-shadow: rgba(7,7,16,0.38);
            --accent-soft:  rgba(129,140,248,0.18);
            --green-soft:   rgba(125,211,160,0.18);
            --red-soft:     rgba(240,138,156,0.18);
            --yellow-soft:  rgba(232,200,122,0.18);
            --cyan-soft:    rgba(125,200,240,0.18);
        }
        :root[data-theme="light"] {
            --bg:           #F6F7F9;
            --panel:        #FCFCFA;
            --fg:           #20232A;
            --fg-dim:       #626771;
            --accent:       #5145E5;
            --green:        #3F7D3F;
            --red:          #B23B3B;
            --yellow:       #9A6A00;
            --cyan:         #2B6CB0;
            --border:       #D9DCE2;
            --current:      #ECEEFA;
            --context-surface: #FFFFFF;
            --context-edge: rgba(255,255,255,0.92);
            --context-shadow: rgba(52,57,77,0.16);
            --accent-soft:  rgba(81,69,229,0.12);
            --green-soft:   rgba(63,125,63,0.14);
            --red-soft:     rgba(178,59,59,0.12);
            --yellow-soft:  rgba(154,106,0,0.14);
            --cyan-soft:    rgba(43,108,176,0.12);
        }
        /* A single indigo that gives white text good contrast in both modes. */
        :root {
            --primary: #5145E5;
            --mono-font: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
                'Liberation Mono', 'DejaVu Sans Mono', monospace;
        }

        * {
            box-sizing: border-box;
            scrollbar-color: rgba(128,128,128,0.55) transparent;
            scrollbar-width: thin;
        }
        html, body {
            background: var(--bg);
            color: var(--fg);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
            font-size: 13px;
            margin: 0; padding: 0;
            min-width: 0;
            overflow-x: auto;
        }
        .font-mono,
        .machine-data {
            font-family: var(--mono-font) !important;
        }
        .sim-panel {
            background: var(--panel);
            color: var(--fg);
            border: 1px solid var(--border);
            border-radius: 2px;
            box-shadow: none;
        }
        .app-shell {
            overflow-x: hidden;
            overflow-y: auto;
            padding-bottom: 42px;
            scroll-padding-bottom: 58px;
        }
        .workspace-primary,
        .workspace-secondary {
            display: grid !important;
            flex: none !important;
            gap: 12px;
            min-width: 0;
            padding: 12px 16px 0;
            width: 100%;
        }
        .workspace-primary {
            grid-template-columns: minmax(0, 2fr) minmax(0, 2fr) minmax(0, 1fr);
            grid-template-rows: minmax(0, 1fr);
            height: 560px;
            min-height: 560px;
        }
        .workspace-secondary {
            grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
            grid-template-rows: minmax(0, 1fr);
            height: 680px;
            min-height: 680px;
            padding-bottom: 16px;
        }
        .panel-frame {
            height: 100%;
            min-height: 0;
            min-width: 0;
            overflow: hidden;
            padding: 12px !important;
        }
        .panel-header {
            border-bottom: 1px solid var(--border);
            flex: 0 0 auto;
            gap: 6px;
            margin-bottom: 8px;
            min-height: 32px;
            padding: 0 0 7px;
        }
        .panel-title {
            color: var(--fg);
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.025em;
            line-height: 1.2;
        }
        .asm-listing {
            color: var(--fg);
            min-width: 360px;
            padding: 0 2px 12px;
        }
        .asm-listing-head,
        .asm-line {
            display: grid;
            grid-template-columns: 20px 16px 92px minmax(58px, max-content) minmax(100px, 1fr);
            align-items: center;
            column-gap: 6px;
        }
        .asm-listing-head {
            background: var(--panel);
            border-bottom: 1px solid var(--border);
            color: var(--fg-dim);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.08em;
            padding: 2px 8px 7px;
            position: sticky;
            text-transform: uppercase;
            top: 0;
            z-index: 1;
        }
        .asm-head-bp { grid-column: 1; }
        .asm-head-pc { grid-column: 3; }
        .asm-head-instruction { grid-column: 4 / -1; }
        .asm-symbol-kind {
            color: var(--fg-dim);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }
        .asm-symbol,
        .panel-context-band {
            background: var(--context-surface);
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
            border-radius: 2px;
            box-shadow:
                inset 0 1px 0 var(--context-edge),
                0 5px 12px var(--context-shadow);
        }
        .asm-symbol {
            margin: 8px 8px 10px;
            padding: 8px 10px 9px;
        }
        .panel-context-band {
            padding: 8px 10px;
        }
        .asm-symbol-meta {
            align-items: center;
            display: flex;
            gap: 8px;
            justify-content: space-between;
        }
        .asm-symbol-address {
            color: var(--fg-dim);
            font-size: 11px;
        }
        .asm-symbol-name {
            color: var(--fg);
            font-size: 14px;
            font-weight: 700;
            line-height: 1.25;
            margin-top: 3px;
        }
        .asm-line {
            border-left: 3px solid transparent;
            color: var(--fg-dim);
            cursor: default;
            min-height: 29px;
            padding: 4px 8px 4px 5px;
            white-space: nowrap;
        }
        .asm-line[data-addr] {
            cursor: pointer;
        }
        .asm-line:hover {
            background: var(--accent-soft);
            color: var(--fg);
        }
        .asm-line:focus-visible {
            background: var(--accent-soft);
            outline: 1px solid var(--accent);
            outline-offset: -1px;
        }
        .asm-current {
            background: var(--current);
            border-left-color: var(--accent);
            color: var(--fg);
        }
        .asm-bp-marker {
            color: var(--red);
            font-size: 12px;
            text-align: center;
        }
        .asm-pc-marker {
            color: var(--accent);
            font-size: 13px;
            font-weight: 700;
            text-align: center;
        }
        .asm-address {
            color: var(--fg-dim);
            font-size: 11px;
        }
        .asm-mnemonic {
            color: var(--accent);
            font-weight: 600;
        }
        .asm-current .asm-mnemonic {
            color: var(--green);
        }
        .asm-operands {
            color: inherit;
            overflow: visible;
        }
        .asm-raw-line {
            color: var(--fg-dim);
            padding: 7px 10px;
            white-space: pre-wrap;
        }
        .asm-empty {
            color: var(--fg-dim);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 12px;
            padding: 22px 12px;
            text-align: center;
        }
        .panel-source .panel-header {
            flex-wrap: wrap;
        }
        .panel-source .context-controls {
            flex: 1 1 100%;
            flex-wrap: nowrap;
            min-width: 0;
            order: 3;
            overflow-x: auto;
        }
        .diagnostics-stack {
            height: 100%;
            min-height: 0;
            overflow-y: auto;
        }
        .diagnostic-section {
            flex: 0 0 auto;
            min-width: 0;
        }
        .decode-section { order: 1; }
        .pipeline-section,
        .mc-section { order: 2; }
        .pipeline-context {
            margin-bottom: 8px;
        }
        .pipeline-context .context-controls {
            padding-top: 0;
        }
        .pipeline-context .state-legend {
            border-top: 1px solid var(--border);
            padding: 7px 0 5px;
        }
        .pipeline-trace-note {
            color: var(--fg-dim);
            font-family: var(--mono-font);
            font-size: 11px;
            line-height: 1.4;
            padding-top: 2px;
        }
        .pipeline-splitter {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 2px;
            height: 500px;
            min-height: 440px;
            width: 100%;
        }
        .pipeline-splitter .q-splitter__separator {
            background: var(--border) !important;
            cursor: col-resize;
            width: 1px !important;
        }
        .pipeline-splitter .q-splitter__separator:hover {
            background: var(--accent) !important;
        }
        .pipeline-pane {
            height: 100%;
            min-height: 0;
            min-width: 0;
        }
        .pipeline-pane-title {
            background: var(--bg);
            border-bottom: 1px solid var(--border);
            color: var(--fg-dim);
            flex: 0 0 auto;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.055em;
            padding: 8px 10px;
        }
        .pipeline-visualization-pane .pipeline-pane-title {
            box-shadow: inset 0 -2px 0 var(--accent);
            color: var(--fg);
        }
        .pipeline-pane-scroll {
            flex: 1 1 auto;
            min-height: 0;
            overflow: auto;
            padding: 8px;
            width: 100%;
        }
        .pipeline-register-view .pipeline-latches {
            font-size: 12px !important;
            line-height: 1.5 !important;
            margin: 0 0 12px;
            width: 100%;
        }
        .pipeline-latches thead th {
            background: var(--bg);
            position: sticky;
            top: 0;
            z-index: 1;
        }
        .pipeline-latches tbody tr {
            border-bottom: 1px solid var(--border);
        }
        .pipeline-metrics {
            display: grid;
            font-family: var(--mono-font);
            gap: 1px;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .pipeline-metrics > span {
            display: flex;
            flex-direction: column;
            gap: 1px;
            min-width: 0;
            padding: 6px 8px;
        }
        .pipeline-metrics small {
            color: var(--fg-dim);
            font-size: 10px;
        }
        .pipeline-metrics strong {
            font-size: 12px;
            font-weight: 700;
        }
        .pipeline-timeline-view .pipeline-gantt {
            font-size: 11px !important;
            line-height: 1.4 !important;
        }
        .pipeline-gantt tbody tr {
            border-bottom: 1px solid var(--border);
        }
        .pipeline-gantt tbody tr:hover td {
            background: var(--current);
        }
        .bottom-status {
            position: fixed;
            inset: auto 0 0 0;
            flex-wrap: nowrap;
            gap: 16px;
            height: 42px;
            max-height: 42px;
            min-height: 42px;
            overflow-x: auto;
            padding: 0 16px;
            z-index: 4;
        }
        .status-separator {
            background: var(--border);
            flex: 0 0 1px;
            height: 20px;
        }
        .app-topbar {
            background: var(--panel);
            border-bottom: 1px solid var(--border);
        }
        .app-brandbar {
            min-height: 44px;
            padding: 6px 16px;
            gap: 10px;
        }
        .app-logo {
            width: 26px;
            height: 26px;
            flex: 0 0 26px;
            object-fit: contain;
        }
        .app-title {
            color: var(--fg);
            font-size: 17px;
            font-weight: 750;
            letter-spacing: -0.025em;
        }
        .app-subtitle {
            color: var(--fg-dim);
            font-size: 12px;
        }
        .app-status {
            color: var(--green);
            font-size: 11px;
            font-weight: 600;
            flex: 0 1 420px;
            min-width: 80px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .execution-toolbar {
            min-height: 50px;
            padding: 7px 16px;
            gap: 6px;
            border-top: 1px solid var(--border);
            background: var(--bg);
            overflow-x: auto;
            flex-wrap: nowrap;
        }
        .toolbar-separator {
            height: 24px;
            margin: 0 4px;
            background: var(--border);
        }
        .control-group-label {
            color: var(--fg-dim);
            font-size: 11px;
            font-weight: 650;
            letter-spacing: 0.02em;
            white-space: nowrap;
        }
        .run-speed-slider {
            flex: 0 0 120px;
            width: 120px;
        }
        .run-speed-value {
            color: var(--fg-dim);
            font-family: var(--mono-font);
            font-size: 11px;
            min-width: 50px;
            white-space: nowrap;
        }
        .context-controls {
            gap: 6px;
            padding: 4px 0 8px;
            flex-wrap: wrap;
        }
        .context-expansion {
            color: var(--fg);
            border-bottom: 1px solid var(--border);
            margin-bottom: 4px;
        }
        .context-expansion .q-item {
            min-height: 34px;
            padding: 2px 0;
        }
        .q-card {
            background: var(--panel) !important;
            color: var(--fg) !important;
            border: 1px solid var(--border);
            border-radius: 2px !important;
            box-shadow: none !important;
        }
        .q-btn {
            background: var(--panel) !important;
            color: var(--fg) !important;
            border: 1px solid var(--border) !important;
            border-radius: 2px !important;
            font-family: inherit !important;
            font-size: 12px !important;
            font-weight: 500 !important;
            text-transform: none !important;
            letter-spacing: 0.01em !important;
            padding: 6px 12px !important;
            min-height: 32px !important;
            box-shadow: none !important;
            transition: none !important;
        }
        .q-btn:not(.btn-primary):not(.btn-selected) {
            background: var(--panel) !important;
            color: var(--fg) !important;
        }
        .q-btn:hover {
            background: var(--current) !important;
            color: var(--accent) !important;
            border-color: var(--accent) !important;
        }
        .q-btn.btn-primary {
            background: var(--primary) !important;
            color: #F8F8F4 !important;
            border: 1px solid var(--primary) !important;
        }
        .q-btn.btn-primary:hover {
            background: #3F36B8 !important;
            color: #F8F8F4 !important;
            border-color: #3F36B8 !important;
        }
        .q-btn.btn-selected {
            background: var(--accent-soft) !important;
            color: var(--accent) !important;
            border-color: var(--accent) !important;
        }
        .q-tab {
            background: transparent !important;
            color: var(--fg-dim) !important;
            border-radius: 2px !important;
            text-transform: none !important;
            font-family: inherit !important;
        }
        .q-tab--active {
            color: var(--accent) !important;
            background: var(--current) !important;
        }
        .q-splitter__separator { background: var(--border) !important; }
        .q-scrollarea { background: transparent; }
        .q-field--filled .q-field__control {
            background: var(--panel) !important;
            border-radius: 2px !important;
            border: 1px solid var(--border) !important;
        }
        .q-field--filled .q-field__control:before,
        .q-field--filled .q-field__control:after { border-bottom: none !important; }
        .q-field__native, .q-field__input { color: var(--fg) !important; }
        .q-field__label { color: var(--fg-dim) !important; }
        .q-field--focused .q-field__control {
            border-color: var(--accent) !important;
            box-shadow: none !important;
            outline: 2px solid var(--accent) !important;
            outline-offset: 1px;
        }
        .q-btn:focus-visible,
        .q-tab:focus-visible,
        .q-item:focus-visible,
        .q-toggle:focus-within,
        .q-slider:focus-within,
        .nicegui-codemirror .cm-editor.cm-focused {
            outline: 2px solid var(--accent) !important;
            outline-offset: 2px;
            box-shadow: none !important;
        }
        .q-btn.btn-danger-subtle {
            background: var(--red-soft) !important;
            color: var(--red) !important;
            border-color: var(--red) !important;
        }
        .q-btn.btn-warning-subtle {
            background: var(--yellow-soft) !important;
            color: var(--yellow) !important;
            border-color: var(--yellow) !important;
        }
        .decode-view {
            color: var(--fg);
            font-size: 12px;
            line-height: 1.5;
            min-width: 0;
        }
        .decode-context {
            margin: 2px 0 10px;
        }
        .decode-identity {
            display: flex;
            align-items: baseline;
            flex-wrap: wrap;
            gap: 6px 10px;
            margin-bottom: 6px;
        }
        .decode-mnemonic {
            color: var(--accent);
            font-size: 16px;
            letter-spacing: 0.02em;
        }
        .decode-mnemonic-invalid { color: var(--red); }
        .decode-family { color: var(--fg-dim); }
        .decode-pc {
            color: var(--fg-dim);
            font-size: 11px;
            white-space: nowrap;
        }
        .decode-raw {
            color: var(--fg-dim);
            margin-left: auto;
            white-space: nowrap;
        }
        .decode-assembly {
            color: var(--cyan);
            font-weight: 500;
            overflow-wrap: anywhere;
        }
        .decode-effect {
            color: var(--fg);
            margin-top: 2px;
            overflow-wrap: anywhere;
        }
        .decode-expanded,
        .decode-detail {
            color: var(--fg-dim);
            font-size: 11px;
            margin-top: 3px;
            overflow-wrap: anywhere;
        }
        .decode-encoding-label {
            color: var(--fg-dim);
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.08em;
            margin-top: 10px;
            text-align: center;
            text-transform: uppercase;
        }
        .decode-bitfield-scroll {
            overflow-x: auto;
            padding: 3px 0 2px;
        }
        .decode-bitfield {
            color: var(--fg-dim);
            display: flex;
            justify-content: center;
            min-width: max-content;
        }
        .decode-bitfield svg {
            display: block;
            height: auto;
            max-width: none;
        }
        .decode-bitfield svg text { fill: var(--fg); }
        .decode-bitfield svg line {
            stroke: var(--border) !important;
            stroke-width: 1 !important;
        }
        .decode-bitfield svg .decode-field {
            stroke: var(--border);
            fill-opacity: 0.18 !important;
        }
        .decode-bitfield svg .decode-field-opcode { fill: var(--accent) !important; }
        .decode-bitfield svg .decode-field-register { fill: var(--cyan) !important; }
        .decode-bitfield svg .decode-field-immediate { fill: var(--yellow) !important; }
        .decode-bitfield svg .decode-field-control { fill: var(--green) !important; }
        .decode-bitfield svg .decode-field-unused { fill: var(--fg-dim) !important; }
        .decode-bitfield svg .decode-field-invalid { fill: var(--red) !important; }
        .decode-empty,
        .decode-bitfield-error {
            color: var(--fg-dim);
            font-size: 12px;
            padding: 8px 0;
        }
        .decode-bitfield-error { color: var(--red); }
        .state-legend {
            align-items: center;
            color: var(--fg-dim);
            display: flex;
            flex-wrap: wrap;
            font-family: var(--mono-font);
            font-size: 11px;
            gap: 4px 12px;
            line-height: 1.4;
            padding: 4px 0 7px;
        }
        .state-legend-item {
            align-items: baseline;
            display: inline-flex;
            gap: 4px;
            white-space: nowrap;
        }
        .state-legend-key {
            font-weight: 700;
            min-width: 12px;
            text-align: center;
        }
        .state-marker-cell {
            box-sizing: border-box;
            min-width: 24px;
            width: 24px;
        }
        .register-table {
            table-layout: auto;
        }
        .register-table th:nth-child(2),
        .register-table td:nth-child(2) {
            width: 30px;
        }
        .register-table th:nth-child(3),
        .register-table td:nth-child(3) {
            width: 52px;
        }
        .register-table thead th,
        .memory-table thead th,
        .cache-table thead th {
            background: var(--bg);
            position: sticky;
            top: 0;
            z-index: 1;
        }
        .mem-table-scroll {
            max-height: 360px;
            overflow: auto;
        }
        .memory-table {
            min-width: 760px;
        }
        .memory-byte-changed {
            box-shadow: inset 0 -2px 0 var(--green);
        }
        .cache-access {
            overflow-x: auto;
        }
        .cache-access-context {
            margin: 0 0 8px;
            min-width: 430px;
        }
        .cache-access-primary,
        .cache-access-meta,
        .mc-context-main,
        .mc-context-meta,
        .trap-entry-head,
        .trap-entry-meta {
            align-items: baseline;
            display: flex;
            flex-wrap: wrap;
        }
        .cache-access-primary {
            gap: 6px 10px;
        }
        .cache-access-kind {
            color: var(--fg-dim);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.08em;
        }
        .cache-access-address {
            color: var(--accent);
            font-size: 14px;
        }
        .cache-access-meta {
            color: var(--fg-dim);
            gap: 4px 14px;
            margin-top: 3px;
        }
        .cache-access-detail {
            min-width: 430px;
            padding: 0 2px;
        }
        .cache-table-scroll {
            border: 1px solid var(--border);
            flex: 0 0 360px;
            height: 360px;
            max-height: 360px;
            min-height: 280px;
            overflow: auto;
        }
        .cache-table {
            min-width: 580px;
            table-layout: fixed;
        }
        .cache-data-cell {
            min-width: 180px;
            vertical-align: top;
        }
        .cache-word-grid {
            display: grid;
            gap: 3px;
            grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
            min-width: 0;
        }
        .cache-word {
            background: var(--bg);
            border: 1px solid var(--border);
            display: grid;
            gap: 1px;
            grid-template-columns: 22px minmax(64px, 1fr);
            padding: 2px 4px;
            white-space: nowrap;
        }
        .cache-word-index {
            color: var(--fg-dim);
            font-size: 10px;
        }
        .cache-state-marker + .cache-state-marker {
            margin-left: 5px;
        }
        .mc-view {
            padding: 2px 0 8px;
        }
        .mc-context {
            margin-bottom: 9px;
        }
        .mc-context-main {
            gap: 6px 10px;
        }
        .mc-mnemonic {
            color: var(--accent);
            font-size: 15px;
        }
        .mc-pc {
            color: var(--fg);
        }
        .mc-context-main > span:not(.mc-pc),
        .mc-context-meta {
            color: var(--fg-dim);
        }
        .mc-context-meta {
            gap: 4px 14px;
            margin-top: 3px;
        }
        .mc-stage-label,
        .trap-history-heading {
            color: var(--fg-dim);
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .mc-stage-track {
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 4px;
            overflow-x: auto;
            padding: 5px 0 8px;
        }
        .mc-stage {
            flex: 0 0 auto;
            min-width: 54px;
            padding: 5px 8px;
            text-align: center;
            white-space: nowrap;
        }
        .mc-stage-active {
            background: var(--current);
            box-shadow: inset 0 -2px 0 var(--accent);
            font-weight: 700;
        }
        .mc-stage-future {
            opacity: 0.72;
        }
        .mc-stall-badge {
            background: var(--red);
            border-radius: 2px;
            color: var(--panel);
            font-size: 10px;
            font-weight: 700;
            margin-left: 3px;
            padding: 1px 4px;
        }
        .trap-log {
            font-size: 11px;
            line-height: 1.55;
            padding: 4px 2px 12px;
        }
        .trap-latest {
            margin-bottom: 12px;
        }
        .trap-entry-head {
            gap: 4px 9px;
        }
        .trap-cause {
            color: var(--fg);
            font-weight: 600;
        }
        .trap-cycle {
            color: var(--fg-dim);
            margin-left: auto;
        }
        .trap-entry-meta {
            color: var(--fg-dim);
            gap: 3px 14px;
            margin-top: 3px;
        }
        .trap-history-heading {
            border-bottom: 1px solid var(--border);
            padding: 0 2px 5px;
        }
        .trap-history-row {
            border-bottom: 1px solid var(--border);
            padding: 8px 2px;
        }
        .trap-empty {
            font-family: var(--mono-font);
            font-size: 12px;
            padding: 8px 2px;
        }
        .pipeline-latches {
            margin: 4px 6px 8px;
        }
        .pipeline-gantt {
            min-width: max-content;
        }
        .pipeline-gantt thead th {
            background: var(--bg);
            position: sticky;
            top: 0;
            z-index: 2;
        }
        .pipeline-gantt th:first-child,
        .pipeline-gantt td:first-child {
            background: var(--panel);
            left: 0;
            position: sticky;
            z-index: 1;
        }
        .pipeline-gantt thead th:first-child {
            background: var(--bg);
            z-index: 3;
        }
        .pipeline-gantt [aria-current="true"] {
            box-shadow: inset 0 -2px 0 var(--accent);
        }
        /* CodeMirror owns its own colors via the selected theme; only fix type/size here. */
        .nicegui-codemirror .cm-editor {
            font-size: 13px !important;
            height: 100% !important;
        }
        .nicegui-codemirror .cm-editor .cm-scroller {
            font-family: var(--mono-font) !important;
        }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(128,128,128,0.40); border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(128,128,128,0.65); }
        .nicegui-content { padding: 0 !important; height: 100dvh !important; overflow: hidden !important; }
        .q-page { min-height: 100dvh !important; padding: 0 !important; }
        .q-layout { min-height: 100dvh !important; }
        @media (min-width: 1024px) and (max-width: 1439px) {
            .workspace-primary {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                grid-template-rows: 520px 320px;
                height: 852px;
                min-height: 852px;
            }
            .panel-registers {
                grid-column: 1 / -1;
            }
            .workspace-secondary {
                grid-template-columns: minmax(0, 1fr);
                grid-template-rows: 680px 820px;
                height: 1512px;
                min-height: 1512px;
            }
            .panel-memory {
                min-height: 680px;
            }
            .panel-diagnostics {
                min-height: 820px;
            }
            .pipeline-splitter {
                height: 560px;
            }
        }
        @media (max-width: 1023px) {
            .workspace-primary,
            .workspace-secondary {
                grid-template-columns: minmax(0, 1fr);
                grid-template-rows: none;
                height: auto;
                min-height: 0;
            }
            .panel-frame {
                height: auto;
                min-height: 380px;
            }
            .panel-source,
            .panel-assembly {
                min-height: 460px;
            }
            .panel-memory,
            .panel-diagnostics {
                min-height: 580px;
            }
            .app-subtitle { display: none; }
            .q-drawer { max-width: 100vw; }
        }
        @media (max-width: 767px) {
            .pipeline-splitter.q-splitter--vertical {
                flex-direction: column !important;
                height: 720px;
            }
            .pipeline-splitter .q-splitter__before {
                flex: 0 0 260px !important;
                height: 260px !important;
                width: 100% !important;
            }
            .pipeline-splitter .q-splitter__after {
                flex: 1 1 auto !important;
                height: 460px !important;
                width: 100% !important;
            }
            .pipeline-splitter .q-splitter__separator {
                display: none;
            }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                transition-duration: 0.01ms !important;
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
            }
        }
    </style>
    ''')
