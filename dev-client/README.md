# auth-system dev client

Manual end-to-end test harness for the auth-system backend. Vite + React + TypeScript + Tailwind. Three tabs (Public / Account / Admin) covering every public, authenticated, and admin auth flow.

## Quickstart

```bash
npm install
npm run dev
```

Open http://localhost:5173.

The backend must be running with `ENVIRONMENT=development` so verification, password reset, and invite codes print to the console. Copy the codes from the backend console into the relevant client form to complete each flow.

## Configuration

Set `VITE_API_BASE_URL` if the backend is not on `http://localhost:8000`:

```bash
VITE_API_BASE_URL=http://localhost:9000 npm run dev
```

## Notes

- The access token is stored in `localStorage` under `dev_client_access_token`. The refresh token is set as an httponly cookie by the backend.
- "Sign in with Google" returns 503 unless `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are configured in the backend `.env`.
- Without Redis, the backend's rate limiter and token blacklist degrade silently — flows still work.
