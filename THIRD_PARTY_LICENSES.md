# Third-party licenses

Dependencies installed into `.venv` (direct and transitive), with the license each
declares. Generated from installed package metadata; regenerate after changing deps:

```bash
make licenses
```

**Summary: no copyleft obligations attach to this project.** No GPL, AGPL, LGPL, or
SSPL dependency is present. Everything is permissive (MIT / BSD / Apache-2.0 / PSF),
except `certifi` (MPL-2.0), whose file-level copyleft applies only to modifications of
certifi's own files — it imposes nothing on this project's code, which merely imports it.

This project's own code is [0BSD](LICENSE). Note that 0BSD waives attribution *for this
project's code only*: anyone redistributing a bundle that vendors the dependencies below
must still honour their notice requirements (MIT/BSD/Apache all require preserving their
copyright notices).

## Packages (67)

| package | version | license |
|---|---|---|
| annotated-types | 0.7.0 | MIT License |
| anyio | 4.14.2 | MIT |
| attrs | 26.1.0 | MIT |
| beautifulsoup4 | 4.15.0 | MIT License |
| certifi | 2026.6.17 | Mozilla Public License 2.0 (MPL 2.0) |
| cffi | 2.1.0 | MIT-0 |
| charset-normalizer | 3.4.9 | MIT |
| click | 8.4.2 | BSD-3-Clause |
| cobble | 0.1.4 | BSD License |
| cryptography | 49.0.0 | Apache-2.0 OR BSD-3-Clause |
| defusedxml | 0.7.1 | Python Software Foundation License |
| et_xmlfile | 2.0.0 | MIT License |
| flatbuffers | 25.12.19 | Apache Software License |
| greenlet | 3.5.3 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD License |
| httpx-sse | 0.4.3 | MIT |
| idna | 3.18 | BSD-3-Clause |
| iniconfig | 2.3.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| lxml | 6.1.1 | BSD-3-Clause |
| magika | 0.6.3 | Apache Software License |
| mammoth | 1.11.0 | BSD License |
| markdownify | 1.2.3 | MIT License |
| markitdown | 0.1.6 | MIT |
| mcp | 1.28.1 | MIT License |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| onnxruntime | 1.27.0 | MIT License |
| openpyxl | 3.1.5 | MIT License |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| pandas | 3.0.3 | BSD License |
| pdfminer.six | 20260107 | MIT |
| pdfplumber | 0.11.10 | MIT License |
| pillow | 12.3.0 | MIT-CMU |
| pip | 26.1.2 | MIT |
| playwright | 1.61.0 | Apache-2.0 |
| pluggy | 1.6.0 | MIT License |
| protobuf | 7.35.1 | 3-Clause BSD License |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.13.4 | MIT |
| pydantic-settings | 2.14.2 | MIT |
| pydantic_core | 2.46.4 | MIT |
| pyee | 13.0.1 | MIT License |
| Pygments | 2.20.0 | BSD-2-Clause |
| PyJWT | 2.13.0 | MIT |
| pypdfium2 | 5.11.0 | BSD-3-Clause, Apache-2.0, dependency licenses |
| pytest | 9.1.1 | MIT |
| pytest-asyncio | 1.4.0 | Apache-2.0 |
| python-dateutil | 2.9.0.post0 | BSD License; Apache Software License |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| python-pptx | 1.0.2 | MIT License |
| referencing | 0.37.0 | MIT |
| requests | 2.34.2 | Apache Software License |
| rpds-py | 2026.6.3 | MIT |
| setuptools | 66.1.1 | MIT License |
| six | 1.17.0 | MIT License |
| soupsieve | 2.8.4 | MIT |
| sse-starlette | 3.4.5 | BSD-3-Clause |
| starlette | 1.3.1 | BSD-3-Clause |
| typing-inspection | 0.4.2 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.7.0 | MIT |
| uvicorn | 0.51.0 | BSD-3-Clause |
| xlsxwriter | 3.2.9 | BSD License |

## Not installed via pip

| component | license | note |
|---|---|---|
| Chromium (Playwright browser binary) | BSD-3-Clause + others | downloaded at runtime into `~/.cache/ms-playwright`, not redistributed by this project |
| Node.js (for `@playwright/mcp`) | MIT | installed to `~/.local`, not redistributed |
| `@playwright/mcp` | Apache-2.0 | fetched by `npx` at runtime |

