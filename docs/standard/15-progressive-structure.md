# 15. Structure Thresholds

The folder shape is fixed (Section 2.1), so there is no promotion step and no "when do
I restructure?" judgement. What remains are a few size signals that mean a model
problem, not a layout problem:

| Signal | Threshold (starting point, tune per project) | What it actually means |
|---|---|---|
| `<module>/application/<aggregate>.py` | > ~7 public methods, > ~200 lines, or > 5 constructor params (checker warns) | The aggregate is probably doing too much. Look at the aggregate boundary before splitting the service. |
| `<module>/domain/model/aggregate.py` | > ~400 lines or > ~7 invariants | God Aggregate. Split into two aggregate modules. |
| `<module>/domain/model/ports.py` | > ~8 protocols in one aggregate module | The aggregate depends on too much of the outside world. |
| `src/commons/` | anything beyond IDs, VOs, enums/catalogues, and cross-aggregate domain services | ARCH-047 violation, or the aggregates are wrongly separated. |
| Cross-aggregate atomicity needed | more than occasionally | The aggregate boundaries are drawn wrong (Section 3.6). Redraw before adding any coordinating construct. |
| Reads through the aggregate | complex joins, reporting, dashboard shapes | Introduce a dedicated read model in `<context>/read/` (Section 2.5). |
| Cross-context integration | more than one team, or independent deployability needed | Move from an in-process gateway to async events + ACL as the default. |
| Outbound adapters of one kind | many (e.g. 5+ external clients) in one module | Sub-folder within that module's `adapters/`. |

Most of these signals point at the model, not at the folders. That is the intended
effect of fixing the shape: when something hurts, the structure is no longer a
candidate explanation. (ARCH-041)
