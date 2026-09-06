# 15. Progressive Structure

Thresholds are starting points; tune them per project. A module is promoted to a
package only past these thresholds (ARCH-041).

| Signal | Threshold (starting point, tune per project) | Action |
|---|---|---|
| `domain/model.py` size | > ~400 lines or > 2 aggregates | promote to `domain/model/` package |
| `domain/model/ports.py` | > ~8 port definitions, or 3+ aggregates | split into `ports/` package, one module per aggregate |
| Application service class | > ~7 public methods, > ~200 lines, > 5 constructor params (checker warns), or a second aggregate appears | split the general service into a second module (move methods + their colocated commands; only `providers.py` changes) |
| Reads through the aggregate | complex joins, reporting, dashboard shapes | introduce a dedicated read model outside the domain |
| Context sub-areas | 2+ separable areas each with its own aggregates | activate the `<module>/` level |
| Cross-context integration | > 1 team, or independent deployability needed | move from in-process gateway to async events + ACL as the default |
| Infrastructure adapters of one kind | many (e.g. 5+ external clients) | sub-folder within `infrastructure/` |
