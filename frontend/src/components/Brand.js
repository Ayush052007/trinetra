/**
 * TRINETRA brand mark.
 *
 * The eye-and-magnifier device from the project logo, drawn as inline SVG so it
 * stays crisp at any size, needs no asset request, and works offline.
 *
 * The iris is split deliberately: a segmented blue half (analysed, connected
 * data) against a plain grey half (the data still unexamined), with the
 * magnifier at the centre — which is the idea the mark carries.
 */

import { html } from "../lib/ui.js";

const NAVY = "#16294D";
const BLUE = "#2E6CB0";
const GREY = "#8A93A1";

const OUTER = 23;   // iris outer radius
const INNER = 12.8; // iris inner radius (where the lens sits)

/** Point on a circle centred at (64, 64). */
function pt(deg, r) {
  const rad = (deg * Math.PI) / 180;
  return [64 + r * Math.cos(rad), 64 + r * Math.sin(rad)];
}

export function TrinetraLogo({ size = 34, title = "TRINETRA" }) {
  // Left half of the iris, drawn as 11 discrete blue segments.
  const segments = [];
  for (let i = 0; i < 11; i += 1) {
    const a0 = 90 + (i * 180) / 11;
    const a1 = 90 + ((i + 1) * 180) / 11 - 2.4;
    const [x0, y0] = pt(a0, INNER);
    const [x1, y1] = pt(a1, INNER);
    const [x2, y2] = pt(a1, OUTER);
    const [x3, y3] = pt(a0, OUTER);
    segments.push(
      html`<path
        key=${i}
        d=${`M ${x0} ${y0} A ${INNER} ${INNER} 0 0 1 ${x1} ${y1} L ${x2} ${y2} A ${OUTER} ${OUTER} 0 0 0 ${x3} ${y3} Z`}
        fill=${BLUE}
      />`
    );
  }

  return html`<svg
    width=${size} height=${size} viewBox="0 0 128 128"
    xmlns="http://www.w3.org/2000/svg" role="img" aria-label=${title}
    style=${{ display: "block", flex: "none" }}
  >
    <title>${title}</title>

    <!-- three dots above the eye -->
    <circle cx="47" cy="18" r="5" fill=${NAVY} />
    <circle cx="64" cy="14" r="6" fill=${NAVY} />
    <circle cx="81" cy="18" r="5" fill=${NAVY} />

    <!-- eye outline: upper and lower lids meeting at the corners -->
    <path
      d="M 8 64 Q 36 27 64 27 Q 92 27 120 64"
      fill="none" stroke=${NAVY} strokeWidth="7" strokeLinecap="round"
    />
    <path
      d="M 8 64 Q 36 101 64 101 Q 92 101 120 64"
      fill="none" stroke=${NAVY} strokeWidth="7" strokeLinecap="round"
    />

    <!-- iris: grey right half-ring -->
    <path
      d=${`M 64 ${64 - OUTER} A ${OUTER} ${OUTER} 0 0 1 64 ${64 + OUTER} `
        + `L 64 ${64 + INNER} A ${INNER} ${INNER} 0 0 0 64 ${64 - INNER} Z`}
      fill=${GREY}
    />
    <!-- iris: segmented blue left half-ring -->
    ${segments}

    <!-- magnifier handle, drawn under the lens so the lens caps it cleanly -->
    <line
      x1="72.5" y1="72.5" x2="86" y2="86"
      stroke=${NAVY} strokeWidth="8" strokeLinecap="round"
    />

    <!-- magnifier lens -->
    <circle cx="64" cy="64" r="13.4" fill="#ffffff" stroke=${NAVY} strokeWidth="3.2" />
    <path
      d="M 57.5 60 A 7.5 7.5 0 0 1 63 56.2"
      fill="none" stroke=${GREY} strokeWidth="2" strokeLinecap="round" opacity="0.9"
    />
  </svg>`;
}

/** Logo plus wordmark, used in the login header and the app sidebar. */
export function BrandLockup({ size = 34, wordSize = 17, subtitle, stacked = false }) {
  return html`<div className=${`brand-lockup ${stacked ? "stacked" : ""}`}>
    <${TrinetraLogo} size=${size} />
    <div className="brand-lockup-text">
      <div className="brand-lockup-name" style=${{ fontSize: `${wordSize}px` }}>TRINETRA</div>
      ${subtitle ? html`<div className="brand-lockup-sub">${subtitle}</div>` : null}
    </div>
  </div>`;
}
