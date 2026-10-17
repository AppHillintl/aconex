import re
import os

SVG_SRC = r"platform\backend\static\images\master_plan.svg"
SVG_OUT = r"platform\backend\static\images\master_plan_interactive.svg"

PORTFOLIO_PACKAGES_METADATA = {
    "Dp01": {
        "projectId": "DP01",
        "code": "DP01",
        "title": "DP01 - Area 1 Basement & Superstructure",
        "contract_no": "REH.08.25.3121 / 3180",
        "contractor": "Orascom Construction SAE",
        "category": "Wadi Yemm",
        "target": (1020.0, 550.0),
        "box": (980.0, 625.0)
    },
    "Dp02": {
        "projectId": "DP02",
        "code": "DP02",
        "title": "DP02 - Area 2 Basement & Superstructure",
        "contract_no": "REH.08.25.3149 / 3270",
        "contractor": "CCC / ROWAD JV",
        "category": "Wadi Yemm",
        "target": (1005.0, 370.0),
        "box": (1060.0, 330.0)
    },
    "Dp03_x20_West": {
        "projectId": "DP03-West",
        "code": "DP03-W",
        "title": "DP03 West - Buildings & Infrastructure",
        "contract_no": "REH.08.26.3271",
        "contractor": "CCC-ROWAD JV",
        "category": "Wadi Yemm",
        "target": (910.0, 375.0),
        "box": (920.0, 310.0)
    },
    "Dp03-East": {
        "projectId": "DP03-East",
        "code": "DP03-E",
        "title": "DP03 East - Buildings & Infrastructure",
        "contract_no": "REH.08.26.3199",
        "contractor": "Innovo-Redcon JV",
        "category": "Wadi Yemm",
        "target": (770.0, 390.0),
        "box": (640.0, 350.0)
    },
    "Dp04": {
        "projectId": "DP04",
        "code": "DP04",
        "title": "DP04 - Buildings & Infrastructure",
        "contract_no": "REH.08.26.3204",
        "contractor": "Arabian Construction Company (ACC)",
        "category": "Wadi Yemm",
        "target": (750.0, 465.0),
        "box": (640.0, 470.0)
    },
    "DP05": {
        "projectId": "DP05",
        "code": "DP05",
        "title": "DP05 - Buildings & Infrastructure",
        "contract_no": "REH.08.26.3205",
        "contractor": "Orascom Construction SAE",
        "category": "Wadi Yemm",
        "target": (878.0, 515.0),
        "box": (830.0, 615.0)
    },
    "Dpo6": {
        "projectId": "DP06",
        "code": "DP06",
        "title": "DP06 - Buildings & Infrastructure",
        "contract_no": "REH.08.26.3206",
        "contractor": "Hassan Allam Construction",
        "category": "Wadi Yemm",
        "target": (1260.0, 555.0),
        "box": (1240.0, 625.0)
    },
    "Dp07": {
        "projectId": "DP07",
        "code": "DP07",
        "title": "DP07 - Buildings & Infrastructure",
        "contract_no": "REH.08.26.3207",
        "contractor": "CSCEC Egypt",
        "category": "Wadi Yemm",
        "target": (1180.0, 400.0),
        "box": (1310.0, 350.0)
    },
    "Dp08": {
        "projectId": "DP08 - South Golf",
        "code": "DP08",
        "title": "DP08 - South Golf & Logistics",
        "contract_no": "REH0126321300",
        "contractor": "Dar SSH International",
        "category": "Wadi Yemm",
        "target": (980.0, 310.0),
        "box": (1080.0, 240.0)
    },
    "West_x20_canal": {
        "projectId": "West Canal",
        "code": "West Canal",
        "title": "West Canal - Dry Bulk Excavation",
        "contract_no": "REH.08.25.3107",
        "contractor": "Orascom Construction SAE",
        "category": "Infrastructure & Strategic Projects",
        "target": (1390.0, 440.0),
        "box": (1485.0, 390.0)
    },
    "Grand_x20_Canal": {
        "projectId": "Grand Canal",
        "code": "Grand Canal",
        "title": "Grand Canal - Dry Bulk Excavation",
        "contract_no": "REH.08.26.3200",
        "contractor": "Hassan Allam Construction",
        "category": "Infrastructure & Strategic Projects",
        "target": (280.0, 360.0),
        "box": (130.0, 360.0)
    },
    "Ring_x20_Road": {
        "projectId": "Ring Road",
        "code": "Ring Road",
        "title": "REH East Ring Road - Infrastructure Works",
        "contract_no": "REH.04.25.3091",
        "contractor": "Al Horema / Orascom",
        "category": "Infrastructure & Strategic Projects",
        "target": (1380.0, 292.0),
        "box": (1380.0, 215.0)
    },
    "STP": {
        "projectId": "STP",
        "code": "STP",
        "title": "STP - Sewage Treatment Plant",
        "contract_no": "REH.08.25.3046",
        "contractor": "Hassan Allam Construction",
        "category": "Infrastructure & Strategic Projects",
        "target": (803.7, 209.0),
        "box": (680.0, 175.0)
    },
    "MSS": {
        "projectId": "MMS",
        "code": "MSS",
        "title": "MSS - Main Power Supply Substation",
        "contract_no": "REH.08.25.3044",
        "contractor": "El Sewedy Electric T&D - ROWAD Consortium",
        "category": "Infrastructure & Strategic Projects",
        "target": (808.1, 184.3),
        "box": (870.0, 130.0)
    },
    "RO": {
        "projectId": "RO Plant",
        "code": "RO Plant",
        "title": "RO Plant - Potable Water Desalination",
        "contract_no": "REH.08.25.3045",
        "contractor": "Orascom-Trojan-Cox JV",
        "category": "Infrastructure & Strategic Projects",
        "target": (638.8, 15.7),
        "box": (520.0, 30.0)
    }
}

custom_defs = """
<defs>
  <marker id="arrow-emerald" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#10b981"/>
  </marker>
  <marker id="arrow-cyan" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#06b6d4"/>
  </marker>
  <filter id="callout-shadow" x="-30%" y="-30%" width="160%" height="160%">
    <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#000000" flood-opacity="0.8"/>
  </filter>
  <filter id="glow-emerald" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur stdDeviation="5" result="blur"/>
    <feMerge>
      <feMergeNode in="blur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
</defs>
<style>
.synoptic-area {
    cursor: pointer !important;
    transition: fill 0.22s ease, stroke 0.22s ease, stroke-width 0.22s ease, filter 0.22s ease;
}
.synoptic-area.wy-area {
    fill: rgba(16, 185, 129, 0.16) !important;
    stroke: #10b981 !important;
    stroke-width: 2.2px !important;
}
.synoptic-area.strat-area {
    fill: rgba(6, 182, 212, 0.16) !important;
    stroke: #06b6d4 !important;
    stroke-width: 2.2px !important;
}
.synoptic-area:hover, .synoptic-area.is-hovered {
    stroke-width: 3.8px !important;
    filter: drop-shadow(0 0 14px rgba(56, 189, 248, 0.95)) !important;
}
.synoptic-area.wy-area:hover, .synoptic-area.wy-area.is-hovered {
    fill: rgba(16, 185, 129, 0.38) !important;
    stroke: #34d399 !important;
    filter: drop-shadow(0 0 14px rgba(52, 211, 153, 0.95)) !important;
}
.synoptic-area.strat-area:hover, .synoptic-area.strat-area.is-hovered {
    fill: rgba(6, 182, 212, 0.38) !important;
    stroke: #38bdf8 !important;
    filter: drop-shadow(0 0 14px rgba(56, 189, 248, 0.95)) !important;
}
.callout-group {
    cursor: pointer !important;
    transition: transform 0.18s ease, filter 0.18s ease;
}
.callout-group rect {
    transition: fill 0.18s ease, stroke 0.18s ease, stroke-width 0.18s ease;
}
.callout-group:hover rect, .callout-group.is-hovered rect {
    fill: rgba(15, 23, 42, 0.98) !important;
    stroke-width: 2.5px !important;
}
.callout-group.wy-group:hover rect, .callout-group.wy-group.is-hovered rect {
    stroke: #34d399 !important;
    filter: drop-shadow(0 0 10px rgba(52, 211, 153, 0.85)) !important;
}
.callout-group.strat-group:hover rect, .callout-group.strat-group.is-hovered rect {
    stroke: #38bdf8 !important;
    filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.85)) !important;
}
.callout-group:hover, .callout-group.is-hovered {
    transform: translateY(-1.5px);
}
</style>
"""

with open(SVG_SRC, 'r', encoding='utf-8') as f:
    svg_raw = f.read()

# Make svg responsive
svg_mod = re.sub(r'<svg\s+([^>]*?)\bwidth=[\'"][^\'"]*[\'"]\s+height=[\'"][^\'"]*[\'"]', r'<svg \1 width="100%" height="100%" preserveAspectRatio="xMidYMid meet"', svg_raw, count=1)
# Inject defs and styles
svg_mod = re.sub(r'(<svg[^>]*>)', r'\1' + custom_defs, svg_mod, count=1)

callouts_svg = ['<g class="portfolio-callouts-layer">']

for aid, meta in PORTFOLIO_PACKAGES_METADATA.items():
    pid = meta['projectId']
    code = meta['code']
    title = meta['title']
    cno = meta['contract_no']
    ctor = meta['contractor']
    cat = meta['category']
    is_wy = (cat == 'Wadi Yemm')
    accent = "#10b981" if is_wy else "#06b6d4"
    marker = "arrow-emerald" if is_wy else "arrow-cyan"
    area_cls = "wy-area" if is_wy else "strat-area"
    group_cls = "wy-group" if is_wy else "strat-group"

    # Replace path attributes
    pattern = re.compile(rf'(<path\s+[^>]*?id=[\'"]{re.escape(aid)}[\'"][^>]*?)(/?>)', re.IGNORECASE)

    def replace_path(m, _acls=area_cls, _aid=aid, _pid=pid, _code=code, _title=title, _cno=cno, _ctor=ctor, _cat=cat):
        body = m.group(1)
        closer = m.group(2)
        body = re.sub(r'\s+(fill|stroke|stroke-width|class|style)=[\'"][^\'"]*[\'"]', '', body)
        attrs = (
            f' class="synoptic-area {_acls}"'
            f' data-area-id="{_aid}"'
            f' data-project-id="{_pid}"'
            f' data-code="{_code}"'
            f' data-title="{_title}"'
            f' data-contract="{_cno}"'
            f' data-contractor="{_ctor}"'
            f' data-category="{_cat}"'
        )
        return f"{body}{attrs}{closer}"

    svg_mod = pattern.sub(replace_path, svg_mod)

    # Callout Pill Tag
    tx, ty = meta['target']
    bx, by = meta['box']

    dx = tx - bx
    dy = ty - by
    dist = (dx*dx + dy*dy)**0.5
    if dist > 0:
        start_x = bx + (dx / dist) * 48
        start_y = by + (dy / dist) * 16
    else:
        start_x, start_y = bx, by

    bw, bh = 100, 32
    rx, ry = bx - bw/2, by - bh/2
    sub_label = "Wadi Yemm" if is_wy else "Infrastructure"

    callout_block = f"""
    <g class="callout-group {group_cls}" data-area-id="{aid}" data-project-id="{pid}" data-code="{code}" data-title="{title}" data-contract="{cno}" data-contractor="{ctor}" data-category="{cat}">
        <circle cx="{tx}" cy="{ty}" r="4" fill="{accent}" stroke="#ffffff" stroke-width="1.5" />
        <circle cx="{tx}" cy="{ty}" r="8" fill="none" stroke="{accent}" stroke-width="1.2" opacity="0.6" />
        <line x1="{start_x:.1f}" y1="{start_y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{accent}" stroke-width="1.6" stroke-dasharray="4,2.5" marker-end="url(#{marker})" />
        <rect x="{rx:.1f}" y="{ry:.1f}" width="{bw}" height="{bh}" rx="7" fill="rgba(15, 23, 42, 0.94)" stroke="{accent}" stroke-width="1.6" filter="url(#callout-shadow)" pointer-events="all" />
        <text x="{bx:.1f}" y="{by-3:.1f}" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11" font-weight="900" fill="#ffffff" letter-spacing="0.5" pointer-events="none">{code}</text>
        <text x="{bx:.1f}" y="{by+9:.1f}" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="8.5" font-weight="700" fill="{accent}" pointer-events="none">{sub_label}</text>
    </g>
    """
    callouts_svg.append(callout_block)

callouts_svg.append('</g>')
all_callouts_str = "\n".join(callouts_svg)
svg_mod = re.sub(r'(</svg>)', all_callouts_str + r'\1', svg_mod, count=1)

with open(SVG_OUT, 'w', encoding='utf-8') as f:
    f.write(svg_mod)

print("Generated interactive SVG:", SVG_OUT, "size:", os.path.getsize(SVG_OUT))
