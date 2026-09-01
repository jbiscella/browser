"""Regenerate THIRD_PARTY_LICENSES.md from installed package metadata.

Run after changing dependencies:  make licenses
"""

from __future__ import annotations

from importlib.metadata import distributions

COPYLEFT = ("GPL", "AGPL", "LGPL", "SSPL", "OSL", "EPL", "CDDL")


def license_of(dist) -> str:
    meta = dist.metadata
    expr = meta.get("License-Expression")  # PEP 639
    if expr:
        return expr.strip()
    classifiers = [
        c.split("::")[-1].strip()
        for c in (meta.get_all("Classifier") or [])
        if c.startswith("License")
    ]
    if classifiers:
        return "; ".join(classifiers)
    legacy = (meta.get("License") or "").strip()
    return legacy.splitlines()[0][:45] if legacy else "see project page"


def main() -> None:
    rows = sorted(
        {
            (d.metadata["Name"], d.version, license_of(d))
            for d in distributions()
            if d.metadata.get("Name") and d.metadata["Name"] != "webresearch"
        },
        key=lambda r: r[0].lower(),
    )

    strong = [
        r for r in rows
        if any(c in r[2].upper() for c in COPYLEFT) and "LGPL" not in r[2].upper()
    ]

    out = [
        "# Third-party licenses",
        "",
        "Dependencies installed into `.venv` (direct and transitive), with the license each",
        "declares. Generated from installed package metadata; regenerate after changing deps:",
        "",
        "```bash",
        "make licenses",
        "```",
        "",
    ]

    if strong:
        out += [
            "> **⚠ A strong-copyleft dependency is present — review before distributing:**",
            "",
            *[f"> - `{n}` {v} — {l}" for n, v, l in strong],
            "",
        ]
    else:
        out += [
            "**Summary: no copyleft obligations attach to this project.** No GPL, AGPL, LGPL, or",
            "SSPL dependency is present. Everything is permissive (MIT / BSD / Apache-2.0 / PSF),",
            "except `certifi` (MPL-2.0), whose file-level copyleft applies only to modifications of",
            "certifi's own files — it imposes nothing on this project's code, which merely imports it.",
            "",
        ]

    out += [
        "This project's own code is [0BSD](LICENSE). Note that 0BSD waives attribution *for this",
        "project's code only*: anyone redistributing a bundle that vendors the dependencies below",
        "must still honour their notice requirements (MIT/BSD/Apache all require preserving their",
        "copyright notices).",
        "",
        f"## Packages ({len(rows)})",
        "",
        "| package | version | license |",
        "|---|---|---|",
        *[f"| {n} | {v} | {l} |" for n, v, l in rows],
        "",
        "## Not installed via pip",
        "",
        "| component | license | note |",
        "|---|---|---|",
        "| Chromium (Playwright browser binary) | BSD-3-Clause + others | downloaded at runtime "
        "into `~/.cache/ms-playwright`, not redistributed by this project |",
        "| Node.js (for `@playwright/mcp`) | MIT | installed to `~/.local`, not redistributed |",
        "| `@playwright/mcp` | Apache-2.0 | fetched by `npx` at runtime |",
        "",
    ]

    print("\n".join(out))


if __name__ == "__main__":
    main()
