export interface Paste {
  slug: string;
  content: string;
  owner_github_id: string;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  size: number;
}

export interface Me {
  github_id: string;
  login: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// The web sign-in/refresh response: access token only. The refresh token is delivered in an
// HttpOnly cookie the backend sets, never in the body (see api.ts). TokenPair is the CLI's
// body shape, kept here for reference.
export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export type Expiry = "" | "1h" | "1d" | "1w";
