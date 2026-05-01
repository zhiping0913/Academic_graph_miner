# 🐛 Bug Fix: Forward/Backward Citation Direction (2026-05-01)

## Issue Summary
The forward/backward citation direction logic was **inverted** for OpenCitations data in `fitch_citations.py`, causing incorrect data merging.

## Problem Details

**Location**: `fitch_citations.py:221-234` in `fetch_combined_data()` function

### Before Fix (WRONG)
```python
# Citations: 谁引用了这篇论文 (Backward)  ← WRONG LABEL & WRONG TARGET
oc_citations = oc_data.get('citations', [])
if isinstance(oc_citations, list):
    for citing_doi in oc_citations:
        if citing_doi:
            b_set.add(citing_doi.lower())  # ← Should be f_set!

# References: 这篇论文引用了谁 (Forward)  ← WRONG LABEL & WRONG TARGET  
oc_refs = oc_data.get('references', [])
if isinstance(oc_refs, list):
    for cited_doi in oc_refs:
        if cited_doi:
            f_set.add(cited_doi.lower())  # ← Should be b_set!
```

### After Fix (CORRECT)
```python
# Citations: 谁引用了这篇论文 (Forward)  ← CORRECT LABEL & TARGET
oc_citations = oc_data.get('citations', [])
if isinstance(oc_citations, list):
    for citing_doi in oc_citations:
        if citing_doi:
            f_set.add(citing_doi.lower())  # ✓ Correct target

# References: 这篇论文引用了谁 (Backward)  ← CORRECT LABEL & TARGET
oc_refs = oc_data.get('references', [])
if isinstance(oc_refs, list):
    for cited_doi in oc_refs:
        if cited_doi:
            b_set.add(cited_doi.lower())  # ✓ Correct target
```

## Correct Terminology

Per user specification:
- **Forward (前向)** = Citations = **Who cites this paper** (被引用)
- **Backward (后向)** = References = **What this paper cites** (参考文献)

## Data Source Verification

All three API sources now correctly implement this mapping:

### Semantic Scholar (S2)
- `citations` field → f_set (Forward) ✓
- `references` field → b_set (Backward) ✓

### Crossref
- `reference` field → b_set (Backward only) ✓
- No citations data provided

### OpenCitations (NOW FIXED)
- `/citations/{doi}` endpoint (citing DOI) → f_set (Forward) ✓
- `/references/{doi}` endpoint (cited DOI) → b_set (Backward) ✓

## Test Results

### Test Case 1: 10.1038/s41567-019-0584-7
- **Forward**: 186 (who cites this paper) ✓
- **Backward**: 30 (what this paper cites) ✓

### Test Case 2: 10.1364/OE.25.023567
- **Forward**: 11 (who cites this paper) ✓
- **Backward**: 40 (what this paper cites) ✓

## Files Modified

1. **fitch_citations.py** (lines 221-234)
   - Fixed OpenCitations direction mapping
   - Updated comments to correct labels

2. **MODULE_FITCH_CITATIONS.md**
   - Updated documentation with correct Forward/Backward definitions
   - Added three-source merge strategy explanation
   - Clarified API endpoint meanings

3. **CLAUDE.md** (line 84-93)
   - Updated paper structure documentation
   - Added proper Forward/Backward definitions

4. **test_api_sources.py**
   - Fixed sample data display section for new simplified format

5. **compare_citations.py**
   - Fixed OpenCitations comments and labels
   - Updated display labels for clarity

## Impact

- **Severity**: Critical - affected all OpenCitations data
- **Scope**: Only OpenCitations source was affected (S2 and Crossref were correct)
- **Data Quality**: Now merged correctly across all three sources
- **User Impact**: Citation network mining now produces correct results

## Verification Steps

Run test scripts to verify:
```bash
python test_api_sources.py      # Single DOI detailed test
python compare_citations.py     # Multi-source comparison
```

Both now correctly show:
- OpenCitations citations → Forward count
- OpenCitations references → Backward count
- Proper deduplication across merged sources

---

**Fixed on**: 2026-05-01  
**Impact**: Critical data mapping correction  
**Status**: ✅ Verified and tested
