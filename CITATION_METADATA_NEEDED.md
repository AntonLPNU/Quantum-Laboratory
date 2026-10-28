# Метадані цитування та відкриті реквізити

The CFF 1.2.0 schema requires an `authors` list, `cff-version`, `message` and `title`. The owner has now explicitly identified **Anton Volos (Волос Антон Володимирович)** as software author. `CITATION.cff` records this name and version 0.5.0; it does not assert university copyright ownership.

The machine-readable citation is now present. The project code license is MIT
(scoped to author-owned code and documentation). Release date, repository URL,
ORCID, affiliation and DOI are intentionally omitted until confirmed:

```yaml
authors:
  - family-names: Volos
    given-names: Anton
cff-version: "1.2.0"
message: "If you use this software, please cite it using these metadata."
title: "Quantum Laboratory"
version: "0.5.0"
```

Before publication, confirm:

1. Whether to add an affiliation and ORCID to the software citation.
2. The actual public release date and final repository URL. DOI/Zenodo identifiers remain absent until assigned.
3. Whether external research datasets and generated Stage 5B records may be redistributed with the software.

Suggested Ukrainian prose: Волос А. В. *Quantum Laboratory*: програмний комплекс для моделювання квантових систем, версія 0.5.0, Research Preview. Додати посилання на конкретний GitHub Release після оприлюднення.

Suggested English prose: Volos, Anton. *Quantum Laboratory*, version 0.5.0, software, Research Preview. Add the exact GitHub Release link after publication. The software citation does not replace references to Hensen datasets or scientific papers.

Schema reference: [Citation File Format 1.2.0 schema guide](https://github.com/citation-file-format/citation-file-format/blob/main/schema-guide.md).
