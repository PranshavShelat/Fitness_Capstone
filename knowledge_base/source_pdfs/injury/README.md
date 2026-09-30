# Injury-prevention sources

`injury_knowledge.py` cites these papers. Download each PDF into this folder
with the filename shown, so every citation in the report has its source document
in the repo. The two government documents it also cites are already in
`../workouts/` (US Army FM 7-22 and HHS Physical Activity Guidelines).

| Save as | Paper | Where to get it |
|---|---|---|
| `kolber2010_shoulder_injuries_resistance_training.pdf` (**not downloaded yet**) | Kolber MJ, Beekhuizen KS, Cheng MS, Hellman MA. Shoulder injuries attributed to resistance training: a brief review. J Strength Cond Res. 2010;24(6):1696-1704. doi:10.1519/JSC.0b013e3181dc4330 | https://nsuworks.nova.edu/hpd_pt_facarticles/92/ (NSU repository) |
| `callaghan_mcgill2001_disc_herniation_repetitive_flexion.pdf` (**not available - paywalled**) | Callaghan JP, McGill SM. Intervertebral disc herniation: studies on a porcine model exposed to highly repetitive flexion/extension motion with compressive force. Clin Biomech. 2001;16(1):28-37. doi:10.1016/S0268-0033(00)00063-2 | https://www.sciencedirect.com/science/article/abs/pii/S0268003300000632 (paywalled: use PES library access) |
| `hewett2005_knee_valgus_acl_risk.pdf` (in repo) | Hewett TE, Myer GD, Ford KR, et al. Biomechanical measures of neuromuscular control and valgus loading of the knee predict anterior cruciate ligament injury risk in female athletes: a prospective study. Am J Sports Med. 2005;33(4):492-501. doi:10.1177/0363546504269591 | https://journals.sagepub.com/doi/10.1177/0363546504269591 or the ResearchGate / Academia copies |
| `escamilla1998_knee_biomechanics_open_closed_chain.pdf` (in repo) | Escamilla RF, Fleisig GS, Zheng N, Barrentine SW, Wilk KE, Andrews JR. Biomechanics of the knee during closed kinetic chain and open kinetic chain exercises. Med Sci Sports Exerc. 1998;30(4):556-569. | https://www.researchgate.net/publication/13714406 |
| `schoenfeld2010_squatting_kinematics_kinetics_page1.pdf` (in repo, page 1 only - the cited passage is on it) | Schoenfeld BJ. Squatting kinematics and kinetics and their application to exercise performance. J Strength Cond Res. 2010;24(12):3497-3506. doi:10.1519/JSC.0b013e3181bac2d7 | https://kinetisense.com/wp-content/uploads/2020/04/Squatting-Kinematics-and-Kinetics-and-Their-Application-to-Exercise-Performance.pdf |

Once a file is here, set its `"file"` entry in `SOURCES` (in `injury_knowledge.py`)
to `knowledge_base/source_pdfs/injury/<filename>`.

Note: `pdf_knowledge.py` indexes every PDF under `source_pdfs/`, so after you add
these, the embedding cache (`knowledge_base_embeddings.npz`) rebuilds once on the
next plan request, which takes a minute. Retrieval filters by folder, so these
chunks will not leak into workout or meal plans. Feeding them to the report through
RAG is the next step (step 4).

## Status (29 Sep 2026)

In repo and checked against the report text: Hewett 2005, Escamilla 1998,
Schoenfeld 2010 (page 1). Kolber 2010 and Callaghan & McGill 2001 are cited from
their published abstracts, which were checked against every claim the report
makes from them; their full PDFs are not in the repo.
