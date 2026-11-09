# F1-A: all-absent penalty fix (2026-09-14; live-tested 16/16; hash-identical; /tmp cleaned)

## Change (financial_calculations.py, inside compute_session_shares early-return, ~:240-300)
ONE serial edit: when present_count==0 AND absent_unexcused_count>0, compute penalty bases
from U (unit_price per absentee, or PricingTable count_min(U,5)/U; institute count_min(U,15)/U).
T_total/I_total/finals stay 0. Error behavior mirrors H5 (400 bad grade / 500 missing tariff).
present>0 path: zero lines touched (category mapping intentionally duplicated in-branch).

## Verify
ast.parse OK; real `import main` CLEAN; live 16/16, zero Tracebacks:
- Regression: mixed session numbers byte-identical to pre-fix (200000/80000/100000/40000).
- All-absent (3×, price 100000): penT=300000, penI=99999 (3×33333, rem 1 undistributed —
  same philosophy as mixed sessions), T=I=0.
- H8-gap ALIVE for first time: pending shows penalty_only=True amount=300000; admin settle→200;
  is_penalty_settled=1; re-settle→400; gone from pending.
