\# Meaning Intelligence



> \*\*Meta-Intelligence Theory and Layered Applications\*\*

> Aligned with the canon \*Meaning Intelligence: The Cognitive Operating System of Meaning Civilization\* V7.0



\[!\[Live Page](https://img.shields.io/badge/live-page-00e5ff?style=flat-square)](https://sara-protocol.github.io/meaning-intelligence/)

\[!\[Release](https://img.shields.io/github/v/release/sara-protocol/meaning-intelligence?style=flat-square\&color=bb86fc)](https://github.com/sara-protocol/meaning-intelligence/releases/latest)

\[!\[License](https://img.shields.io/badge/license-MIT-8b95a5?style=flat-square)](LICENSE)



\---



\*\*Meaning Intelligence is the \*directional regulation\* of other intelligent activities.\*\* It is not a fourth kind of intelligence standing alongside logical, computational, and perceptual intelligence, but a \*meta-layer\* above them that constrains their direction. Its question is not \*"can it be done"\* but \*"is it worth doing — worth it for whom, and at what scale?"\*



\[中文版](README.md)



\## The Six-Layer Stack



The six layers fall into \*\*three bands\*\* by cognitive distance:



| Band | Layer | Name | Solves |

|---|---|---|---|

| \*\*Interface\*\* | L1 | Cognitive Load Reduction | \*Information cannot get in\* |

| \*\*Interface\*\* | L2 | Experiential Rendering | \*Information cannot get in\* |

| \*\*Processing\*\* | L3 | Meaning Generation | \*Meaning cannot get out\* |

| \*\*Processing\*\* | L4 | Value Assessment | \*Meaning cannot get out\* |

| \*\*Meta\*\* | L5 | Direction Selection | \*Direction cannot be held\* |

| \*\*Meta\*\* | L6 | Recursive Reflection and Review | \*Direction cannot be held\* |



\*\*Only the meta band can rewrite the premises of the layers below it\*\* — this is the formal signature of "meta".



L6's output is written back as L1's input. The six layers form a \*\*closed spiral\*\*, not a one-way pipeline.



\## What's in this Repository



| Directory | Contents |

|---|---|

| `whitepaper/` | Bilingual public-release white paper v1.0 (19 pages, 7 tables, 2 figures), DOCX + PDF, generation scripts |

| `msi/` | Meaning Intelligence Demonstration System — six-act Manim animation, single-file interactive page, per-layer screenshots |

| `toolkit/` | 11 fillable checklists derived from Canon Appendix A (A.1–A.10) |

| `docs/` | Architecture, evidence levels, failure matrix, glossary, roadmap, automation governance |

| `tools/` | Zero-dependency publisher, PDF/HTML verifiers, issue-form validator |



\## Quick Start



```bash

\# 1. Clone

git clone https://github.com/sara-protocol/meaning-intelligence.git

cd meaning-intelligence



\# 2. Read the white paper

\#    → whitepaper/dist/意义智能\_元智能理论与分层应用\_公开发布白皮书\_v1.0\_中英双语.pdf



\# 3. Watch the six-act animation

\#    → msi/MeaningIntelligenceScene.mp4



\# 4. Open the interactive dashboard

\#    → msi/meaning\_intelligence.html  (double-click; no server required)



\# 5. Rebuild the white paper (optional)

python whitepaper/build\_whitepaper.py



\# 6. Re-render the animation (optional, requires manim)

cd msi \&\& python run.ps1     # Windows

cd msi \&\& bash run.sh        # macOS / Linux

