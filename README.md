# Option Bazaar

Shared development/test workspace for the Option Bazaar trading application.

## Current scope

- Responsive dark trading dashboard
- Frontend + backend in one repository
- Mock/test market data first
- Paper trading first
- Price ladder with separate BUY/SELL per row
- Ladder price click fills Limit Price
- Factor-J signal/audit placeholders
- FYERS adapter comes after the non-broker flow is stable
- Live orders remain disabled until explicitly tested

## Codespaces

Open this repository in GitHub Codespaces. The dev container forwards:

- Frontend: port 5173
- Backend API: port 8000

Run `npm run dev` from the repository root after the Codespace finishes setup.

This repository is a development environment, not a claim of production readiness.
