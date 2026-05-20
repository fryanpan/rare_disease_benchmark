# CD59 Deficiency Trace — Delphi-style Debate Team v2

> **Note:** This is a modified-prompt capture for illustration purposes, not the exact benchmark run.
> The diagnostic pipeline and specialist architecture are identical to the benchmark condition;
> the only modification is that the orchestrator was instructed to include specialist outputs
> verbatim rather than producing only the final top-5.

**Case:** 7322911-1 — 16-year-old female, 4,546 characters
**Ground truth:** CD59 deficiency syndrome (Primary CD59 deficiency)
**Tokens:** 9,681 input, 459 output

---

All three Round 2 specialists have returned. Here is the complete verbose trace of the entire Delphi consultation:

---

# Delphi Diagnostic Consultation — Full Trace

## Round 1 Specialist Outputs

### Specialist 1 — Pattern Matcher (Round 1)

1. CD59 deficiency (Primary CD59 deficiency / HACD59, OMIM #612300) | conf=5 | Autosomal recessive complement regulatory defect in a consanguineous family presenting with the canonical triad of infection-triggered recurrent demyelinating neuropathy (GBS/CIDP), recurrent angioedema, and white matter lesions, with dramatic response to FFP replacing the missing complement inhibitor.
2. Hereditary angioedema type I (C1-inhibitor deficiency) | conf=2 | Recurrent angioedema with FFP responsiveness fits, but C1-INH deficiency is autosomal dominant, does not cause demyelinating neuropathy, and does not explain white matter lesions or infection-triggered quadriplegia.
3. Chronic inflammatory demyelinating polyneuropathy (CIDP) with coincidental urticaria/angioedema | conf=2 | The relapsing demyelinating neuropathy with steroid/IVIG responsiveness and EMG-NCV findings match CIDP, but CIDP alone does not explain the recurrent angioedema, FFP response, or consanguinity pattern.
4. Paroxysmal nocturnal hemoglobinuria (PNH) | conf=1 | PNH involves acquired somatic loss of GPI-anchored proteins including CD59 on hematopoietic cells, causing complement-mediated hemolysis and can cause neuropathy, but it is an acquired clonal disorder of adulthood, not a congenital autosomal recessive condition of childhood.
5. Systemic lupus erythematosus with neuropsychiatric manifestations | conf=1 | White matter lesions, angioedema, and neuropathy can occur in SLE, but the patient had negative lupus-specific autoantibodies, normal complement, and the infantile onset with consanguinity points away from SLE.
6. Complement C2 deficiency with immune dysregulation | conf=1 | Autosomal recessive complement deficiency can cause recurrent infections and immune-mediated disease in consanguineous families, but C2 deficiency typically presents with SLE-like illness and pneumococcal infections, not demyelinating neuropathy.
7. Hereditary angioedema with normal C1-INH (HAE type III, Factor XII mutations) | conf=1 | Recurrent angioedema with infection triggers, but this is typically autosomal dominant and does not cause demyelinating neuropathy or white matter lesions.
8. Acute disseminated encephalomyelitis (ADEM) with recurrent episodes | conf=1 | Post-infectious demyelination with white matter lesions on MRI fits, but ADEM does not explain recurrent angioedema, FFP responsiveness, or the peripheral neuropathy pattern.
9. Metachromatic leukodystrophy | conf=1 | Autosomal recessive demyelinating disease with white matter lesions in a consanguineous family, but it causes progressive (not relapsing) disease, does not feature angioedema, and would show elevated arylsulfatase A deficiency.
10. Mitochondrial disease (MELAS or related) | conf=1 | Consanguinity, elevated LDH, white matter lesions, and episodic neurological deterioration with infection triggers could suggest mitochondrial disease, but normal lactate, normal ammonia, and the prominent angioedema/FFP response are not features of mitochondrial disease.

### Specialist 2 — Mechanism Reasoner (Round 1)

1. Primary CD59 deficiency (OMIM #612300) | conf=5 | Loss of the CD59 complement regulator permits uncontrolled membrane attack complex (MAC) formation on Schwann cells and endothelium, producing recurrent demyelinating neuropathy, angioedema, hemolysis (elevated LDH), cerebellar white matter lesions, and dramatic response to FFP — all in an autosomal recessive pattern consistent with consanguinity.
2. Hereditary angioedema type I (C1-INH deficiency, OMIM #106100) | conf=2 | C1-INH deficiency causes recurrent bradykinin-mediated angioedema responsive to FFP, but it is autosomal dominant, does not cause demyelinating neuropathy or white matter lesions, and does not explain elevated LDH or short stature.
3. Complement factor I deficiency (OMIM #610984) | conf=2 | Autosomal recessive CFI deficiency leads to uncontrolled complement activation with CNS demyelination and infection susceptibility, but angioedema and peripheral demyelinating neuropathy are not prominent features, and FFP response would be less predictable.
4. Chronic inflammatory demyelinating polyradiculoneuropathy (CIDP) with coincident hereditary angioedema | conf=1 | Autoimmune CIDP explains the neuropathy and steroid/IVIG response, but the co-occurrence of angioedema, hemolysis, and white matter lesions in a consanguineous child with FFP responsiveness argues against two separate acquired diseases.
5. Complement factor H deficiency (OMIM #609814) | conf=1 | Autosomal recessive CFH deficiency causes uncontrolled alternative pathway activation with renal and neurological manifestations, but peripheral neuropathy and angioedema are atypical, and renal disease (absent here) is the usual hallmark.
6. Paroxysmal nocturnal hemoglobinuria (PNH) | conf=1 | PNH involves acquired loss of GPI-anchored proteins including CD59, causing hemolysis and thrombosis, but it is an acquired somatic disorder of hematopoietic stem cells, not autosomal recessive, and does not typically present in early childhood with demyelinating neuropathy.
7. Systemic lupus erythematosus with secondary complement consumption | conf=1 | SLE can cause angioedema, CIDP-like neuropathy, and white matter disease through complement-mediated inflammation, but lupus-specific autoantibodies were negative, and the consanguineous/recessive pattern and FFP response are not explained.
8. Hereditary angioedema with normal C1-INH (type III, OMIM #610618) | conf=1 | Gain-of-function mutations in Factor XII or other genes cause angioedema with normal C1-INH, but this does not explain demyelinating neuropathy, white matter lesions, hemolysis, or short stature.
9. Metachromatic leukodystrophy (OMIM #250100) | conf=1 | Autosomal recessive arylsulfatase A deficiency causes progressive demyelination of both central and peripheral nervous systems in children of consanguineous parents, but it does not cause angioedema, is not episodic/relapsing, and does not respond to FFP.
10. Aicardi-Goutieres syndrome (OMIM #225750) | conf=1 | Autosomal recessive interferonopathy causing CNS white matter disease and systemic inflammation in children, but peripheral demyelinating neuropathy, angioedema, and FFP response are not features of this condition.

### Specialist 3 — Differential Excluder (Round 1)

1. Primary CD59 deficiency | conf=5 | Autosomal recessive complement regulator deficiency uniquely explains the triad of recurrent infection-triggered demyelinating neuropathy (GBS/CIDP mimic), recurrent angioedema, and elevated LDH (chronic hemolysis), with FFP response providing the missing complement inhibitor protein, all in the setting of consanguinity.
2. Hereditary angioedema type I (C1-INH deficiency, SERPING1) with coincidental CIDP | conf=2 | Explains angioedema and FFP response, but C1-INH deficiency is autosomal dominant and does not cause demyelinating neuropathy or white matter lesions, making coincidental co-occurrence unlikely.
3. Hereditary angioedema type III (HAE with normal C1-INH, FXII/PLG/ANGPT1/KNG1 mutations) | conf=1 | Could explain recurrent angioedema but fails to explain the demyelinating neuropathy, hemolysis markers, or infection-triggered neurological relapses.
4. C2 complement deficiency | conf=1 | Autosomal recessive complement deficiency that can present with angioedema and autoimmune-like features including SLE-like syndrome, but demyelinating peripheral neuropathy is not a recognized feature.
5. Aicardi-Goutieres syndrome | conf=1 | Autosomal recessive with white matter disease and consanguinity fit, but canonical features (basal ganglia calcification, elevated CSF interferon-alpha, chilblains) are absent, and it does not cause angioedema or relapsing peripheral neuropathy.
6. CIDP with secondary complement dysregulation | conf=1 | The CIDP phenotype fits the neuropathy, but CIDP alone cannot explain angioedema, FFP-specific response over IVIG, or the autosomal recessive inheritance pattern.
7. Paroxysmal nocturnal hemoglobinuria (PNH) | conf=1 | Shares the CD59-deficient pathophysiology (hemolysis, complement activation) but PNH is an acquired somatic PIGA mutation affecting only blood cells, not germline, and does not cause peripheral neuropathy or present in infancy.
8. Metachromatic leukodystrophy | conf=1 | Autosomal recessive demyelinating disease with white matter lesions and peripheral neuropathy, but does not cause angioedema, does not respond to FFP, and typically shows progressive (not relapsing-remitting) course with cognitive decline.
9. Krabbe disease (late-onset) | conf=1 | Autosomal recessive with peripheral demyelinating neuropathy and white matter changes, but does not explain angioedema, lacks relapsing-remitting pattern, and does not respond to FFP.
10. Familial Guillain-Barré syndrome (unknown genetic basis) | conf=1 | Consanguinity and recurrent GBS-like episodes fit, but this entity is poorly defined, does not explain angioedema or hemolysis, and FFP response specifically implicates a missing plasma complement regulator.

---

## Round 1 Aggregation

**Formula:** group_score = Σ (11 − rank) × confidence across all specialists

| Rank | Candidate Disease | group_score | agreement_count |
|------|-------------------|-------------|-----------------|
| 1 | CD59 deficiency | 150 | 3/3 |
| 2 | HAE type I (C1-INH deficiency) | 54 | 3/3 |
| 3 | CIDP (various framings) | 28 | 3/3 |
| 4 | Complement factor I deficiency | 16 | 1/3 |
| 5 | PNH | 16 | 3/3 |
| 6 | HAE type III | 15 | 3/3 |
| 7 | C2 complement deficiency | 12 | 2/3 |
| 8 | SLE | 10 | 2/3 |
| 9 | Metachromatic leukodystrophy | 7 | 3/3 |
| 10 | Aicardi-Goutières syndrome | 7 | 2/3 |
| 11 | Complement factor H deficiency | 6 | 1/3 |
| 12 | ADEM | 3 | 1/3 |
| 13 | Krabbe disease | 2 | 1/3 |
| 14 | Mitochondrial disease (MELAS) | 1 | 1/3 |
| 15 | Familial GBS | 1 | 1/3 |

---

## Round 2 Specialist Outputs

### Specialist 1 — Pattern Matcher (Round 2, Final)

1. CD59 deficiency (Primary CD59 deficiency / HACD59, OMIM #612300) | conf=5 | The group unanimously converged on this with the highest score by a wide margin. The case is a textbook presentation: consanguineous parents, autosomal recessive inheritance, the canonical triad of infection-triggered recurrent demyelinating neuropathy (GBS/CIDP-like), recurrent angioedema, and CNS white matter lesions, with dramatic response to FFP replacing the missing complement regulator. No other diagnosis unifies all features.
2. Hereditary angioedema type I (C1-inhibitor deficiency) | conf=2 | Group consensus (3/3 agreement). Recurrent angioedema with FFP responsiveness is consistent, but autosomal dominant inheritance contradicts consanguinity, and C1-INH deficiency does not cause demyelinating neuropathy or white matter lesions. Retained as the leading alternative angioedema diagnosis.
3. CIDP with coincidental angioedema | conf=1 | Group consensus (3/3 agreement). The relapsing demyelinating neuropathy with steroid/IVIG responsiveness fits CIDP, but this framing fails to explain the angioedema, FFP response, consanguinity, or the unified pathophysiology that CD59 deficiency provides.
4. Complement factor I deficiency | conf=1 | Evaluated per group input (score=16, 1/3 agreement). Factor I deficiency is autosomal recessive and causes complement dysregulation, which could theoretically produce angioedema and neuropathy. However, the classical presentation is recurrent pyogenic infections and atypical hemolytic uremic syndrome, not the specific triad seen here. It does not fit as well as CD59 deficiency.
5. Paroxysmal nocturnal hemoglobinuria (PNH) | conf=1 | Group consensus (3/3 agreement). PNH involves loss of GPI-anchored CD59 on hematopoietic cells causing complement-mediated hemolysis, conceptually linking it to CD59 dysfunction. However, PNH is an acquired somatic clonal disorder of adulthood, not a germline recessive condition presenting in infancy in a consanguineous family.

### Specialist 2 — Mechanism Reasoner (Round 2, Final)

1. Primary CD59 deficiency (OMIM #612300) | conf=5 | The entire phenotype — recurrent infection-triggered demyelinating neuropathy from infancy, recurrent angioedema, cerebellar white matter lesions, elevated LDH (hemolysis), consanguinity (AR inheritance), and dramatic response to FFP (which supplies functional CD59) — is the textbook presentation of CD59 deficiency. No other single diagnosis unifies all features.
2. Hereditary angioedema type I (C1-INH deficiency) | conf=2 | Explains the recurrent angioedema and FFP response, but cannot account for the demyelinating neuropathy, white matter lesions, or hemolysis.
3. PNH (paroxysmal nocturnal hemoglobinuria) | conf=1 | Acquired loss of GPI-anchored proteins including CD59 produces hemolysis and complement-mediated damage, but PNH is a somatic clonal disorder, not autosomal recessive, and does not present in infancy in consanguineous families.
4. CIDP with coincident angioedema | conf=1 | CIDP could explain the relapsing demyelinating neuropathy, but co-occurrence with angioedema, hemolysis, white matter lesions, and AR inheritance pattern is far better explained by CD59 deficiency.
5. Complement factor I deficiency | conf=1 | AR complement dysregulation can cause CNS demyelination and infection susceptibility, but angioedema, peripheral demyelinating neuropathy, hemolysis, and FFP response are not characteristic features.

### Specialist 3 — Differential Excluder (Round 2, Final)

1. Primary CD59 deficiency | conf=5 | The only diagnosis that unifies ALL features: AR inheritance (consanguinity), complement-mediated recurrent demyelinating neuropathy triggered by infections, angioedema, chronic hemolysis (elevated LDH), white matter lesions, and dramatic FFP response providing the missing complement regulator. Pathognomonic fit.
2. Hereditary angioedema type I (C1-INH deficiency) | conf=2 | Explains angioedema and partial FFP response, but autosomal dominant inheritance contradicts consanguinity, and cannot account for demyelinating neuropathy or hemolysis.
3. PNH (paroxysmal nocturnal hemoglobinuria) | conf=1 | Acquired phenocopy of CD59 deficiency sharing hemolysis and complement dysregulation, but somatic PIG-A mutation is not germline, making infantile onset in a consanguineous family implausible.
4. CIDP with complement dysregulation | conf=1 | Captures the relapsing demyelinating neuropathy phenotype but is a descriptive diagnosis that fails to explain angioedema, hemolysis, or FFP-specific response.
5. C2 complement deficiency | conf=1 | [FIRM] AR complement deficiency with angioedema and autoimmune features partially fits, but demyelinating neuropathy and hemolysis are not recognized features; retained over complement factor I deficiency because C2 deficiency has stronger angioedema association.

---

## Final Synthesis

### Convergence Analysis

| Candidate | S1 R2 | S2 R2 | S3 R2 | Specialists in top-5 | Summed Confidence |
|-----------|--------|--------|--------|----------------------|-------------------|
| **CD59 deficiency** | #1 (5) | #1 (5) | #1 (5) | 3/3 | **15** |
| **HAE type I** | #2 (2) | #2 (2) | #2 (2) | 3/3 | **6** |
| **PNH** | #5 (1) | #3 (1) | #3 (1) | 3/3 | **3** |
| **CIDP** | #3 (1) | #4 (1) | #4 (1) | 3/3 | **3** |
| Complement factor I deficiency | #4 (1) | #5 (1) | — | 2/3 | 2 |
| C2 complement deficiency | — | — | #5 (1) [FIRM] | 1/3 | 1 |

**Positions 1–2: Unanimous.** All three specialists placed CD59 deficiency at #1 with maximum confidence (5/5), and HAE type I at #2 with confidence 2. This is extraordinary convergence.

**Positions 3–4: PNH vs. CIDP.** Both appeared in all 3/3 specialists' top-5 with equal summed confidence (3). PNH is ranked higher by the Mechanism Reasoner (#3) and the Excluder (#3) vs. CIDP (#4 and #4), while the Pattern Matcher ranked CIDP higher (#3 vs. #5). By average rank, **PNH edges out CIDP** (3.67 vs. 3.67 — effectively tied, but PNH has two #3 placements vs. CIDP's one #3). PNH also has stronger mechanistic relevance as the acquired phenocopy of CD59 deficiency.

**Position 5: Complement factor I deficiency vs. C2 complement deficiency.** CFI appeared in 2/3 specialists (Pattern Matcher #4, Mechanism Reasoner #5). C2 deficiency appeared in only 1/3 (Excluder #5, marked [FIRM]) with a relatively weak justification ("stronger angioedema association" than CFI). Per the synthesis rules, 2/3 agreement outweighs a single [FIRM] without a compelling unique-insight justification. **Complement factor I deficiency takes #5.**

---

## Final Top 5

1. **Primary CD59 deficiency (OMIM #612300)** — Unanimous #1 across all three specialists in both rounds (conf=5/5 × 3). This autosomal recessive complement regulatory protein deficiency is the only diagnosis that unifies *every* feature of this case: consanguineous parents, infantile-onset recurrent infection-triggered demyelinating neuropathy (GBS/CIDP mimic), recurrent angioedema, cerebellar and periventricular white matter lesions on MRI, elevated LDH and aldolase (chronic complement-mediated hemolysis), short stature, and the pathognomonic dramatic response to fresh frozen plasma (which supplies the missing CD59 protein). The case closely matches published reports (Javadi Parvaneh et al., 2020; Solmaz et al., 2020).

2. **Hereditary angioedema type I (C1-inhibitor deficiency)** — Unanimous #2 across all specialists (conf=2/5 × 3). Explains the angioedema and FFP response, but autosomal dominant inheritance contradicts the consanguinity pattern, and it cannot account for the demyelinating neuropathy, white matter lesions, or hemolysis markers.

3. **Paroxysmal nocturnal hemoglobinuria (PNH)** — Converged in 3/3 specialists' Round 2 top-5. The acquired somatic phenocopy of CD59 deficiency (loss of GPI-anchored CD59 on blood cells), sharing the hemolysis and complement dysregulation mechanism. Excluded as the primary diagnosis because PNH is acquired (not germline), does not present in infancy, and does not cause peripheral demyelinating neuropathy.

4. **Chronic inflammatory demyelinating polyradiculoneuropathy (CIDP) with coincidental angioedema** — Converged in 3/3 specialists. Captures the neuropathy phenotype descriptively but is not a unifying diagnosis — it cannot explain the angioedema, hemolysis, FFP-specific response, or autosomal recessive inheritance pattern.

5. **Complement factor I deficiency (OMIM #610984)** — Converged in 2/3 specialists. Autosomal recessive complement dysregulation with potential for CNS demyelination and infection susceptibility, but angioedema and peripheral neuropathy are not characteristic features, making it a distant alternative to CD59 deficiency.
